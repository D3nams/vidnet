"""
Integration tests for audio extraction functionality.

Tests the integration between audio extraction service and the download manager.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from app.services.audio_extractor import AudioExtractor, audio_extractor
from app.services.download_manager import DownloadManager
from app.models.video import DownloadRequest, VideoMetadata, VideoQuality


class TestAudioExtractionIntegration:
    """Integration tests for audio extraction."""
    
    @pytest.mark.asyncio
    async def test_audio_extractor_initialization(self):
        """Test that audio extractor initializes correctly."""
        with patch('app.services.audio_extractor.AudioExtractor._find_ffmpeg') as mock_find:
            mock_find.return_value = '/usr/bin/ffmpeg'
            
            extractor = AudioExtractor()
            
            assert extractor.ffmpeg_path == '/usr/bin/ffmpeg'
            assert '128kbps' in extractor.supported_qualities
            assert '320kbps' in extractor.supported_qualities
    
    @pytest.mark.asyncio
    async def test_download_manager_has_audio_extractor(self):
        """Test that download manager has audio extractor instance."""
        with patch('app.services.audio_extractor.AudioExtractor._find_ffmpeg') as mock_find:
            mock_find.return_value = '/usr/bin/ffmpeg'
            
            manager = DownloadManager()
            
            assert hasattr(manager, 'audio_extractor')
            assert isinstance(manager.audio_extractor, AudioExtractor)
    
    @pytest.mark.asyncio
    async def test_audio_extraction_workflow_integration(self):
        """Test complete audio extraction workflow integration."""
        with patch('app.services.audio_extractor.AudioExtractor._find_ffmpeg') as mock_find:
            mock_find.return_value = '/usr/bin/ffmpeg'
            
            manager = DownloadManager()
            
            # Mock video metadata
            mock_metadata = VideoMetadata(
                title="Test Audio Video",
                thumbnail="https://example.com/thumb.jpg",
                duration=180,
                platform="youtube",
                available_qualities=[
                    VideoQuality(quality="720p", format="mp4", filesize=1024000, fps=30)
                ],
                audio_available=True,
                original_url="https://youtube.com/watch?v=test123"
            )
            
            # Mock audio extraction result
            mock_audio_result = {
                'success': True,
                'output_path': '/tmp/test_audio.mp3',
                'file_size': 512000,
                'quality': '128kbps',
                'duration': 180,
                'title': 'Test Audio Video',
                'platform': 'youtube',
                'original_url': 'https://youtube.com/watch?v=test123',
                'extraction_details': {'ffmpeg_returncode': 0}
            }
            
            with patch.object(manager.video_processor, 'extract_metadata') as mock_extract, \
                 patch.object(manager.audio_extractor, 'extract_audio') as mock_audio_extract:
                
                mock_extract.return_value = mock_metadata
                mock_audio_extract.return_value = mock_audio_result
                
                # Test validation
                await manager._validate_download_request(DownloadRequest(
                    url="https://youtube.com/watch?v=test123",
                    quality="720p",
                    format="audio",
                    audio_quality="128kbps"
                ))
                
                # Validation should pass without exceptions
                assert True
    
    @pytest.mark.asyncio
    async def test_audio_quality_validation_integration(self):
        """Test audio quality validation in the integrated workflow."""
        with patch('app.services.audio_extractor.AudioExtractor._find_ffmpeg') as mock_find:
            mock_find.return_value = '/usr/bin/ffmpeg'
            
            extractor = AudioExtractor()
            
            # Test supported qualities
            qualities = extractor.get_supported_qualities()
            assert '128kbps' in qualities
            assert '320kbps' in qualities
            
            # Test quality descriptions
            assert 'bitrate' in qualities['128kbps']
            assert 'quality' in qualities['128kbps']
            assert qualities['128kbps']['bitrate'] == '128k'
            assert qualities['320kbps']['bitrate'] == '320k'
    
    @pytest.mark.asyncio
    async def test_global_audio_extractor_instance(self):
        """Test that global audio extractor instance is available."""
        with patch('app.services.audio_extractor.AudioExtractor._find_ffmpeg') as mock_find:
            mock_find.return_value = '/usr/bin/ffmpeg'
            
            # Import should work without errors
            from app.services.audio_extractor import audio_extractor
            
            assert isinstance(audio_extractor, AudioExtractor)
            assert hasattr(audio_extractor, 'extract_audio')
            assert hasattr(audio_extractor, 'get_supported_qualities')
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self):
        """Test error handling in integrated audio extraction."""
        with patch('app.services.audio_extractor.AudioExtractor._find_ffmpeg') as mock_find:
            mock_find.return_value = '/usr/bin/ffmpeg'
            
            extractor = AudioExtractor()
            
            # Test unsupported quality error
            with pytest.raises(Exception) as exc_info:
                await extractor.extract_audio(
                    "https://youtube.com/watch?v=test123",
                    quality="999kbps"
                )
            
            assert "Unsupported audio quality" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_metadata_preservation_integration(self):
        """Test that metadata preservation is integrated correctly."""
        with patch('app.services.audio_extractor.AudioExtractor._find_ffmpeg') as mock_find:
            mock_find.return_value = '/usr/bin/ffmpeg'
            
            extractor = AudioExtractor()
            
            # Mock video metadata
            mock_metadata = VideoMetadata(
                title="Test Song Title",
                thumbnail="https://example.com/thumb.jpg",
                duration=240,
                platform="youtube",
                available_qualities=[
                    VideoQuality(quality="720p", format="mp4", filesize=1024000, fps=30)
                ],
                audio_available=True,
                original_url="https://youtube.com/watch?v=test123"
            )
            
            # Mock FFmpeg processes
            mock_extract_process = AsyncMock()
            mock_extract_process.returncode = 0
            mock_extract_process.communicate.return_value = (b"", b"")
            
            mock_metadata_process = AsyncMock()
            mock_metadata_process.returncode = 0
            mock_metadata_process.communicate.return_value = (b"", b"")
            
            with patch.object(extractor.video_processor, 'extract_metadata') as mock_get_metadata, \
                 patch('asyncio.create_subprocess_exec') as mock_subprocess, \
                 patch('pathlib.Path.exists') as mock_exists, \
                 patch('pathlib.Path.stat') as mock_stat, \
                 patch('pathlib.Path.mkdir') as mock_mkdir:
                
                mock_get_metadata.return_value = mock_metadata
                mock_subprocess.side_effect = [mock_extract_process, mock_metadata_process]
                mock_exists.return_value = True
                mock_stat.return_value.st_size = 512000
                mock_mkdir.return_value = None
                
                result = await extractor.extract_audio(
                    "https://youtube.com/watch?v=test123",
                    quality="128kbps"
                )
                
                # Verify result contains metadata
                assert result['success'] is True
                assert result['title'] == 'Test Song Title'
                assert result['platform'] == 'youtube'
                assert result['quality'] == '128kbps'
                
                # Verify FFmpeg was called twice (extraction + metadata)
                assert mock_subprocess.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__])