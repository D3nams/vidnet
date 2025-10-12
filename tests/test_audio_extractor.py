"""
Unit tests for audio extraction service.

Tests audio extraction functionality, quality options, metadata preservation,
and error handling for videos without audio tracks.
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json

from app.services.audio_extractor import (
    AudioExtractor,
    AudioExtractionError,
    FFmpegNotFoundError,
    NoAudioTrackError,
    AudioQualityError
)
from app.models.video import VideoMetadata, VideoQuality


class TestAudioExtractor:
    """Test cases for AudioExtractor class."""
    
    @pytest.fixture
    def audio_extractor(self):
        """Create AudioExtractor instance for testing."""
        with patch('app.services.audio_extractor.AudioExtractor._find_ffmpeg') as mock_find:
            mock_find.return_value = '/usr/bin/ffmpeg'
            extractor = AudioExtractor()
            return extractor
    
    @pytest.fixture
    def sample_video_metadata(self):
        """Create sample video metadata for testing."""
        return VideoMetadata(
            title="Test Video Title",
            thumbnail="https://example.com/thumb.jpg",
            duration=180,
            platform="youtube",
            available_qualities=[
                VideoQuality(quality="720p", format="mp4", filesize=1024000, fps=30)
            ],
            audio_available=True,
            original_url="https://youtube.com/watch?v=test123"
        )
    
    @pytest.fixture
    def sample_video_metadata_no_audio(self):
        """Create sample video metadata without audio for testing."""
        return VideoMetadata(
            title="Silent Video",
            thumbnail="https://example.com/thumb.jpg",
            duration=60,
            platform="youtube",
            available_qualities=[
                VideoQuality(quality="720p", format="mp4", filesize=512000, fps=30)
            ],
            audio_available=False,
            original_url="https://youtube.com/watch?v=silent123"
        )
    
    def test_find_ffmpeg_success(self):
        """Test successful FFmpeg detection."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            extractor = AudioExtractor()
            assert extractor.ffmpeg_path == 'ffmpeg'
    
    def test_find_ffmpeg_not_found(self):
        """Test FFmpeg not found error."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            
            with pytest.raises(FFmpegNotFoundError):
                AudioExtractor()
    
    def test_supported_qualities(self, audio_extractor):
        """Test supported audio quality options."""
        qualities = audio_extractor.get_supported_qualities()
        
        assert '128kbps' in qualities
        assert '320kbps' in qualities
        assert qualities['128kbps']['bitrate'] == '128k'
        assert qualities['320kbps']['bitrate'] == '320k'
    
    @pytest.mark.asyncio
    async def test_extract_audio_success(self, audio_extractor, sample_video_metadata):
        """Test successful audio extraction."""
        test_url = "https://youtube.com/watch?v=test123"
        
        with patch.object(audio_extractor.video_processor, 'extract_metadata') as mock_metadata:
            mock_metadata.return_value = sample_video_metadata
            
            with patch.object(audio_extractor, '_extract_with_ffmpeg') as mock_extract:
                mock_extract.return_value = {
                    'ffmpeg_returncode': 0,
                    'output_size': 1024000,
                    'command': 'ffmpeg -i test.mp4 output.mp3'
                }
                
                with patch.object(audio_extractor, '_add_metadata_to_file') as mock_metadata_add:
                    mock_metadata_add.return_value = None
                    
                    with patch('pathlib.Path.exists') as mock_exists, \
                         patch('pathlib.Path.stat') as mock_stat, \
                         patch('pathlib.Path.mkdir') as mock_mkdir:
                        
                        mock_exists.return_value = True
                        mock_stat.return_value.st_size = 1024000
                        mock_mkdir.return_value = None
                        
                        result = await audio_extractor.extract_audio(test_url, '128kbps')
                        
                        assert result['success'] is True
                        assert result['quality'] == '128kbps'
                        assert result['title'] == 'Test Video Title'
                        assert result['platform'] == 'youtube'
                        assert result['file_size'] == 1024000
    
    @pytest.mark.asyncio
    async def test_extract_audio_no_audio_track(self, audio_extractor, sample_video_metadata_no_audio):
        """Test audio extraction from video without audio track."""
        test_url = "https://youtube.com/watch?v=silent123"
        
        with patch.object(audio_extractor.video_processor, 'extract_metadata') as mock_metadata:
            mock_metadata.return_value = sample_video_metadata_no_audio
            
            with pytest.raises(NoAudioTrackError):
                await audio_extractor.extract_audio(test_url, '128kbps')
    
    @pytest.mark.asyncio
    async def test_extract_audio_invalid_quality(self, audio_extractor):
        """Test audio extraction with invalid quality."""
        test_url = "https://youtube.com/watch?v=test123"
        
        with pytest.raises(AudioQualityError):
            await audio_extractor.extract_audio(test_url, '999kbps')
    
    @pytest.mark.asyncio
    async def test_extract_with_ffmpeg_success(self, audio_extractor, sample_video_metadata):
        """Test FFmpeg extraction process."""
        test_url = "https://youtube.com/watch?v=test123"
        output_path = Path("/tmp/test_audio.mp3")
        
        # Mock asyncio subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"success", b"")
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_subprocess.return_value = mock_process
            
            with patch('pathlib.Path.exists') as mock_exists:
                mock_exists.return_value = True
                
                with patch('pathlib.Path.stat') as mock_stat:
                    mock_stat.return_value.st_size = 1024000
                    
                    result = await audio_extractor._extract_with_ffmpeg(
                        test_url, output_path, '128kbps', sample_video_metadata
                    )
                    
                    assert result['ffmpeg_returncode'] == 0
                    assert result['output_size'] == 1024000
                    assert 'ffmpeg' in result['command']
    
    @pytest.mark.asyncio
    async def test_extract_with_ffmpeg_failure(self, audio_extractor, sample_video_metadata):
        """Test FFmpeg extraction failure."""
        test_url = "https://youtube.com/watch?v=test123"
        output_path = Path("/tmp/test_audio.mp3")
        
        # Mock failed subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"FFmpeg error: Invalid input")
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_subprocess.return_value = mock_process
            
            with pytest.raises(AudioExtractionError):
                await audio_extractor._extract_with_ffmpeg(
                    test_url, output_path, '128kbps', sample_video_metadata
                )
    
    @pytest.mark.asyncio
    async def test_extract_with_ffmpeg_no_audio_stream(self, audio_extractor, sample_video_metadata):
        """Test FFmpeg extraction when no audio stream is found."""
        test_url = "https://youtube.com/watch?v=test123"
        output_path = Path("/tmp/test_audio.mp3")
        
        # Mock subprocess with no audio stream error
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"Stream map '0:a' matches no streams")
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_subprocess.return_value = mock_process
            
            with pytest.raises(NoAudioTrackError):
                await audio_extractor._extract_with_ffmpeg(
                    test_url, output_path, '128kbps', sample_video_metadata
                )
    
    @pytest.mark.asyncio
    async def test_add_metadata_to_file_success(self, audio_extractor, sample_video_metadata):
        """Test adding metadata to audio file."""
        file_path = Path("/tmp/test_audio.mp3")
        temp_file = Path("/tmp/test_audio.temp.mp3")
        
        # Mock successful metadata addition
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_subprocess.return_value = mock_process
            
            with patch('pathlib.Path.exists') as mock_exists:
                mock_exists.return_value = True
                
                with patch('shutil.move') as mock_move:
                    await audio_extractor._add_metadata_to_file(file_path, sample_video_metadata)
                    
                    # Verify FFmpeg was called with metadata parameters
                    mock_subprocess.assert_called_once()
                    args = mock_subprocess.call_args[0]
                    assert '-metadata' in args
                    assert f'title={sample_video_metadata.title}' in args
    
    @pytest.mark.asyncio
    async def test_add_metadata_to_file_failure(self, audio_extractor, sample_video_metadata):
        """Test metadata addition failure (should not raise exception)."""
        file_path = Path("/tmp/test_audio.mp3")
        
        # Mock failed metadata addition
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"Metadata error")
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_subprocess.return_value = mock_process
            
            with patch('pathlib.Path.exists') as mock_exists:
                mock_exists.return_value = False
                
                # Should not raise exception, just log warning
                await audio_extractor._add_metadata_to_file(file_path, sample_video_metadata)
    
    def test_sanitize_filename(self, audio_extractor):
        """Test filename sanitization."""
        # Test with invalid characters
        result = audio_extractor._sanitize_filename("Test<>:\"/\\|?*Video")
        assert result == "Test_________Video"
        
        # Test with long filename
        long_name = "a" * 150
        result = audio_extractor._sanitize_filename(long_name)
        assert len(result) <= 100
        
        # Test with empty filename
        result = audio_extractor._sanitize_filename("")
        assert result == "audio_extract"
        
        # Test with whitespace
        result = audio_extractor._sanitize_filename("  Test Video  ")
        assert result == "Test Video"
    
    @pytest.mark.asyncio
    async def test_get_audio_info_success(self, audio_extractor):
        """Test getting audio file information."""
        file_path = "/tmp/test_audio.mp3"
        
        # Mock FFprobe output
        mock_info = {
            'format': {
                'duration': '180.5',
                'size': '1024000',
                'bit_rate': '128000',
                'tags': {'title': 'Test Audio'}
            },
            'streams': [{
                'codec_type': 'audio',
                'codec_name': 'mp3',
                'sample_rate': '44100',
                'channels': '2'
            }]
        }
        
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (json.dumps(mock_info).encode(), b"")
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_subprocess.return_value = mock_process
            
            result = await audio_extractor.get_audio_info(file_path)
            
            assert result['duration'] == 180.5
            assert result['size'] == 1024000
            assert result['bitrate'] == 128000
            assert result['codec'] == 'mp3'
            assert result['sample_rate'] == 44100
            assert result['channels'] == 2
    
    @pytest.mark.asyncio
    async def test_get_audio_info_failure(self, audio_extractor):
        """Test getting audio info when FFprobe fails."""
        file_path = "/tmp/test_audio.mp3"
        
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"FFprobe error")
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_subprocess.return_value = mock_process
            
            result = await audio_extractor.get_audio_info(file_path)
            
            assert result == {}
    
    @pytest.mark.asyncio
    async def test_validate_audio_extraction_support_success(self, audio_extractor, sample_video_metadata):
        """Test validation of audio extraction support."""
        test_url = "https://youtube.com/watch?v=test123"
        
        with patch.object(audio_extractor.video_processor, 'extract_metadata') as mock_metadata:
            mock_metadata.return_value = sample_video_metadata
            
            result = await audio_extractor.validate_audio_extraction_support(test_url)
            
            assert result['supported'] is True
            assert result['platform'] == 'youtube'
            assert result['title'] == 'Test Video Title'
            assert result['audio_available'] is True
            assert '128kbps' in result['supported_qualities']
            assert '320kbps' in result['supported_qualities']
    
    @pytest.mark.asyncio
    async def test_validate_audio_extraction_support_no_audio(self, audio_extractor, sample_video_metadata_no_audio):
        """Test validation when video has no audio."""
        test_url = "https://youtube.com/watch?v=silent123"
        
        with patch.object(audio_extractor.video_processor, 'extract_metadata') as mock_metadata:
            mock_metadata.return_value = sample_video_metadata_no_audio
            
            result = await audio_extractor.validate_audio_extraction_support(test_url)
            
            assert result['supported'] is False
            assert result['audio_available'] is False
            assert result['supported_qualities'] == []
            assert 'No audio track available' in result['message']
    
    @pytest.mark.asyncio
    async def test_validate_audio_extraction_support_error(self, audio_extractor):
        """Test validation when video processing fails."""
        test_url = "https://invalid.com/video"
        
        with patch.object(audio_extractor.video_processor, 'extract_metadata') as mock_metadata:
            mock_metadata.side_effect = Exception("Video processing failed")
            
            result = await audio_extractor.validate_audio_extraction_support(test_url)
            
            assert result['supported'] is False
            assert 'error' in result
            assert 'Validation failed' in result['message']
    
    @pytest.mark.asyncio
    async def test_cleanup_temp_files(self, audio_extractor):
        """Test cleanup of temporary audio files."""
        import time
        current_time = time.time()
        old_time = current_time - (25 * 3600)  # 25 hours ago
        new_time = current_time - (1 * 3600)   # 1 hour ago
        
        # Create mock file objects
        old_file_mock = Mock()
        old_file_mock.is_file.return_value = True
        old_file_mock.stat.return_value.st_mtime = old_time
        old_file_mock.__str__ = Mock(return_value="old_audio.mp3")
        
        new_file_mock = Mock()
        new_file_mock.is_file.return_value = True
        new_file_mock.stat.return_value.st_mtime = new_time
        new_file_mock.__str__ = Mock(return_value="new_audio.mp3")
        
        with patch('time.time') as mock_time:
            mock_time.return_value = current_time
            
            # Mock the temp_dir.iterdir() method
            audio_extractor.temp_dir = Mock()
            audio_extractor.temp_dir.iterdir.return_value = [old_file_mock, new_file_mock]
            
            await audio_extractor.cleanup_temp_files(max_age_hours=24)
            
            # Only old file should be deleted
            old_file_mock.unlink.assert_called_once()
            new_file_mock.unlink.assert_not_called()


class TestAudioExtractionIntegration:
    """Integration tests for audio extraction with real scenarios."""
    
    @pytest.mark.asyncio
    async def test_extract_audio_128kbps_quality(self):
        """Test audio extraction with 128kbps quality."""
        # This would be an integration test with real FFmpeg
        # For unit testing, we mock the dependencies
        pass
    
    @pytest.mark.asyncio
    async def test_extract_audio_320kbps_quality(self):
        """Test audio extraction with 320kbps quality."""
        # This would be an integration test with real FFmpeg
        # For unit testing, we mock the dependencies
        pass
    
    @pytest.mark.asyncio
    async def test_extract_audio_with_metadata_preservation(self):
        """Test that metadata is properly preserved in extracted audio."""
        # This would be an integration test with real FFmpeg
        # For unit testing, we mock the dependencies
        pass


if __name__ == "__main__":
    pytest.main([__file__])