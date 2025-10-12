"""
Audio extraction service for VidNet MVP.

This module provides audio extraction from videos using FFmpeg with quality options,
metadata preservation, and comprehensive error handling.
"""

import asyncio
import os
import subprocess
import logging
import tempfile
import shutil
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import json

from app.models.video import VideoMetadata
from app.services.video_processor import VideoProcessor
from app.core.exceptions import (
    ConversionError, VidNetException, ErrorCode, ProcessingTimeoutError
)
from app.core.retry import retry_async


# Configure logging
logger = logging.getLogger(__name__)


class AudioExtractionError(ConversionError):
    """Base exception for audio extraction errors - deprecated, use ConversionError."""
    pass


class FFmpegNotFoundError(VidNetException):
    """Raised when FFmpeg is not available."""
    
    def __init__(self, **kwargs):
        super().__init__(
            message="FFmpeg is not installed or not available in PATH",
            error_code=ErrorCode.INTERNAL_ERROR,
            status_code=500,
            suggestion="Please install FFmpeg to enable audio extraction",
            **kwargs
        )


class NoAudioTrackError(VidNetException):
    """Raised when video has no audio track."""
    
    def __init__(self, **kwargs):
        super().__init__(
            message="This video does not contain an audio track",
            error_code=ErrorCode.AUDIO_NOT_AVAILABLE,
            status_code=400,
            suggestion="Try a different video that contains audio",
            **kwargs
        )


class AudioQualityError(VidNetException):
    """Raised when requested audio quality is not supported."""
    
    def __init__(self, quality: str, **kwargs):
        super().__init__(
            message=f"Audio quality '{quality}' is not supported",
            error_code=ErrorCode.INVALID_QUALITY,
            status_code=400,
            suggestion="Supported qualities: 128kbps, 320kbps",
            **kwargs
        )
        self.details["requested_quality"] = quality


class AudioExtractor:
    """
    Audio extraction service using FFmpeg.
    
    Features:
    - Extract audio from videos as MP3
    - Quality options (128kbps, 320kbps)
    - Metadata preservation
    - Error handling for videos without audio tracks
    """
    
    def __init__(self):
        """Initialize the audio extractor."""
        self.video_processor = VideoProcessor()
        
        # Supported audio qualities
        self.supported_qualities = {
            '128kbps': {
                'bitrate': '128k',
                'quality': '5',  # VBR quality (0-9, lower is better)
                'description': 'Standard quality (128 kbps)'
            },
            '320kbps': {
                'bitrate': '320k',
                'quality': '0',  # VBR quality (0-9, lower is better)
                'description': 'High quality (320 kbps)'
            }
        }
        
        # FFmpeg executable path
        self.ffmpeg_path = self._find_ffmpeg()
        
        # Temporary directory for processing
        self.temp_dir = Path(tempfile.gettempdir()) / "vidnet_audio"
        self.temp_dir.mkdir(exist_ok=True)
    
    def _find_ffmpeg(self) -> str:
        """
        Find FFmpeg executable path.
        
        Returns:
            str: Path to FFmpeg executable
            
        Raises:
            FFmpegNotFoundError: If FFmpeg is not found
        """
        # Try common FFmpeg locations
        possible_paths = [
            'ffmpeg',  # System PATH
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/opt/homebrew/bin/ffmpeg',  # macOS Homebrew
            'C:\\ffmpeg\\bin\\ffmpeg.exe',  # Windows
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run(
                    [path, '-version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    logger.info(f"Found FFmpeg at: {path}")
                    return path
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue
        
        raise FFmpegNotFoundError(
            "FFmpeg not found. Please install FFmpeg and ensure it's in your PATH."
        )
    
    async def extract_audio(
        self,
        video_url: str,
        quality: str = '128kbps',
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract audio from video URL.
        
        Args:
            video_url: URL of the video to extract audio from
            quality: Audio quality ('128kbps' or '320kbps')
            output_path: Optional output file path
            
        Returns:
            Dict containing extraction results
            
        Raises:
            AudioExtractionError: If extraction fails
            NoAudioTrackError: If video has no audio track
            AudioQualityError: If quality is not supported
        """
        try:
            # Validate quality
            if quality not in self.supported_qualities:
                raise AudioQualityError(
                    f"Unsupported audio quality: {quality}. "
                    f"Supported: {', '.join(self.supported_qualities.keys())}"
                )
            
            logger.info(f"Starting audio extraction from {video_url} with quality {quality}")
            
            # Get video metadata to check audio availability
            metadata = await self.video_processor.extract_metadata(video_url)
            
            if not metadata.audio_available:
                raise NoAudioTrackError("Video does not contain an audio track")
            
            # Generate output filename if not provided
            if not output_path:
                safe_title = self._sanitize_filename(metadata.title)
                timestamp = int(asyncio.get_event_loop().time())
                output_path = self.temp_dir / f"{safe_title}_{timestamp}_{quality}.mp3"
            else:
                output_path = Path(output_path)
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Extract audio using FFmpeg
            extraction_result = await self._extract_with_ffmpeg(
                video_url, output_path, quality, metadata
            )
            
            # Add metadata to the extracted file
            await self._add_metadata_to_file(output_path, metadata)
            
            # Get file information
            file_size = output_path.stat().st_size if output_path.exists() else 0
            
            result = {
                'success': True,
                'output_path': str(output_path),
                'file_size': file_size,
                'quality': quality,
                'duration': metadata.duration,
                'title': metadata.title,
                'platform': metadata.platform,
                'original_url': video_url,
                'extraction_details': extraction_result
            }
            
            logger.info(f"Audio extraction completed successfully: {output_path}")
            return result
            
        except (NoAudioTrackError, AudioQualityError):
            raise
        except VideoProcessorError as e:
            raise AudioExtractionError(f"Video processing failed: {str(e)}")
        except Exception as e:
            logger.error(f"Audio extraction failed for {video_url}: {str(e)}")
            raise AudioExtractionError(f"Audio extraction failed: {str(e)}")
    
    async def _extract_with_ffmpeg(
        self,
        video_url: str,
        output_path: Path,
        quality: str,
        metadata: VideoMetadata
    ) -> Dict[str, Any]:
        """
        Extract audio using FFmpeg.
        
        Args:
            video_url: Video URL
            output_path: Output file path
            quality: Audio quality setting
            metadata: Video metadata
            
        Returns:
            Dict with extraction details
            
        Raises:
            AudioExtractionError: If FFmpeg extraction fails
        """
        try:
            quality_config = self.supported_qualities[quality]
            
            # Build FFmpeg command
            cmd = [
                self.ffmpeg_path,
                '-i', video_url,
                '-vn',  # No video
                '-acodec', 'libmp3lame',  # MP3 codec
                '-ab', quality_config['bitrate'],  # Audio bitrate
                '-q:a', quality_config['quality'],  # VBR quality
                '-ar', '44100',  # Sample rate
                '-ac', '2',  # Stereo
                '-y',  # Overwrite output file
                str(output_path)
            ]
            
            logger.debug(f"FFmpeg command: {' '.join(cmd)}")
            
            # Run FFmpeg in a separate process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"FFmpeg failed with return code {process.returncode}: {error_msg}")
                
                # Check for specific error conditions
                if 'No such file or directory' in error_msg:
                    raise AudioExtractionError("Video file not accessible")
                elif 'Invalid data found' in error_msg:
                    raise AudioExtractionError("Invalid video format")
                elif 'Stream map' in error_msg and 'matches no streams' in error_msg:
                    raise NoAudioTrackError("No audio stream found in video")
                else:
                    raise AudioExtractionError(f"FFmpeg extraction failed: {error_msg}")
            
            # Verify output file was created
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise AudioExtractionError("Output file was not created or is empty")
            
            return {
                'ffmpeg_returncode': process.returncode,
                'output_size': output_path.stat().st_size,
                'command': ' '.join(cmd)
            }
            
        except AudioExtractionError:
            raise
        except Exception as e:
            logger.error(f"FFmpeg execution error: {str(e)}")
            raise AudioExtractionError(f"FFmpeg execution failed: {str(e)}")
    
    async def _add_metadata_to_file(self, file_path: Path, metadata: VideoMetadata):
        """
        Add metadata tags to the extracted audio file.
        
        Args:
            file_path: Path to the audio file
            metadata: Video metadata to add
        """
        try:
            # Create temporary file for metadata addition
            temp_file = file_path.with_suffix('.temp.mp3')
            
            # Build FFmpeg command for metadata addition
            cmd = [
                self.ffmpeg_path,
                '-i', str(file_path),
                '-c', 'copy',  # Copy without re-encoding
                '-metadata', f'title={metadata.title}',
                '-metadata', f'comment=Downloaded from {metadata.platform}',
                '-metadata', f'album=VidNet Downloads',
                '-y',  # Overwrite output file
                str(temp_file)
            ]
            
            # Add artist metadata if available (use platform as artist)
            if metadata.platform:
                cmd.extend(['-metadata', f'artist={metadata.platform.title()}'])
            
            logger.debug(f"FFmpeg metadata command: {' '.join(cmd)}")
            
            # Run FFmpeg for metadata addition
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and temp_file.exists():
                # Replace original file with metadata-enhanced version
                shutil.move(str(temp_file), str(file_path))
                logger.debug(f"Metadata added to {file_path}")
            else:
                # If metadata addition fails, keep the original file
                if temp_file.exists():
                    temp_file.unlink()
                logger.warning(f"Failed to add metadata to {file_path}, keeping original")
                
        except Exception as e:
            logger.warning(f"Error adding metadata to {file_path}: {str(e)}")
            # Don't raise exception for metadata errors, just log warning
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for safe file system usage.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Limit length and strip whitespace
        filename = filename.strip()[:100]
        
        # Ensure filename is not empty
        if not filename:
            filename = 'audio_extract'
        
        return filename
    
    async def get_audio_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get information about an audio file using FFprobe.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            Dict with audio file information
        """
        try:
            # Try to find ffprobe (usually comes with FFmpeg)
            ffprobe_path = self.ffmpeg_path.replace('ffmpeg', 'ffprobe')
            
            cmd = [
                ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                info = json.loads(stdout.decode('utf-8'))
                
                # Extract relevant information
                format_info = info.get('format', {})
                streams = info.get('streams', [])
                audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), {})
                
                return {
                    'duration': float(format_info.get('duration', 0)),
                    'size': int(format_info.get('size', 0)),
                    'bitrate': int(format_info.get('bit_rate', 0)),
                    'codec': audio_stream.get('codec_name'),
                    'sample_rate': int(audio_stream.get('sample_rate', 0)),
                    'channels': int(audio_stream.get('channels', 0)),
                    'tags': format_info.get('tags', {})
                }
            else:
                logger.warning(f"FFprobe failed for {file_path}")
                return {}
                
        except Exception as e:
            logger.warning(f"Error getting audio info for {file_path}: {str(e)}")
            return {}
    
    async def validate_audio_extraction_support(self, video_url: str) -> Dict[str, Any]:
        """
        Validate if audio extraction is supported for the given video URL.
        
        Args:
            video_url: Video URL to validate
            
        Returns:
            Dict with validation results
        """
        try:
            # Get video metadata
            metadata = await self.video_processor.extract_metadata(video_url)
            
            return {
                'supported': metadata.audio_available,
                'platform': metadata.platform,
                'title': metadata.title,
                'duration': metadata.duration,
                'audio_available': metadata.audio_available,
                'supported_qualities': list(self.supported_qualities.keys()) if metadata.audio_available else [],
                'message': 'Audio extraction supported' if metadata.audio_available else 'No audio track available'
            }
            
        except VideoProcessorError as e:
            return {
                'supported': False,
                'error': str(e),
                'message': 'Video processing failed'
            }
        except Exception as e:
            return {
                'supported': False,
                'error': str(e),
                'message': 'Validation failed'
            }
    
    def get_supported_qualities(self) -> Dict[str, Dict[str, str]]:
        """
        Get supported audio quality options.
        
        Returns:
            Dict of supported qualities with descriptions
        """
        return self.supported_qualities.copy()
    
    async def cleanup_temp_files(self, max_age_hours: int = 24):
        """
        Clean up temporary audio files older than specified age.
        
        Args:
            max_age_hours: Maximum age in hours for temporary files
        """
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            cleanup_count = 0
            
            for file_path in self.temp_dir.iterdir():
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    
                    if file_age > max_age_seconds:
                        try:
                            file_path.unlink()
                            cleanup_count += 1
                            logger.debug(f"Cleaned up old audio file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to remove old audio file {file_path}: {e}")
            
            if cleanup_count > 0:
                logger.info(f"Cleaned up {cleanup_count} old audio files")
                
        except Exception as e:
            logger.error(f"Error during audio file cleanup: {e}")


# Global audio extractor instance
audio_extractor = AudioExtractor()