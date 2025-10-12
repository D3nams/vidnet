/**
 * VidNet UI Controller
 * Handles all frontend interactions and API communication
 */
class VidNetUI {
    constructor() {
        this.apiBase = '/api/v1';
        this.currentRequest = null;
        this.currentTaskId = null;
        this.progressInterval = null;
        this.cleanupTimer = null;
        this.downloadStartTime = null;
        
        // Initialize analytics manager
        this.analytics = new AnalyticsManager();
        
        // Initialize ad manager
        this.adManager = new AdManager(this.analytics);
        
        // Initialize the UI
        this.init();
    }
    
    /**
     * Initialize the UI and bind event listeners
     */
    init() {
        this.bindEvents();
        this.setupFormValidation();
        this.addPrivacySettingsLink();
        console.log('VidNet UI initialized');
    }
    
    /**
     * Bind all event listeners
     */
    bindEvents() {
        // URL form submission
        const urlForm = document.getElementById('url-form');
        urlForm.addEventListener('submit', (e) => this.handleURLSubmission(e));
        
        // URL input validation
        const urlInput = document.getElementById('video-url');
        urlInput.addEventListener('input', () => this.validateURL());
        urlInput.addEventListener('paste', () => {
            // Validate after paste event completes
            setTimeout(() => this.validateURL(), 100);
        });
        
        // Retry button
        const retryButton = document.getElementById('retry-button');
        retryButton.addEventListener('click', () => this.retryLastRequest());
        
        // Download another video button
        const downloadAnotherBtn = document.getElementById('download-another');
        downloadAnotherBtn.addEventListener('click', () => this.resetUI());
        
        // Privacy settings link (will be added dynamically)
        document.addEventListener('click', (e) => {
            if (e.target.id === 'privacy-settings-link') {
                e.preventDefault();
                this.analytics.showPrivacySettings();
            }
        });
    }
    
    /**
     * Set up real-time URL validation
     */
    setupFormValidation() {
        const urlInput = document.getElementById('video-url');
        const feedback = document.getElementById('url-feedback');
        const errorDiv = document.getElementById('url-error');
        const successDiv = document.getElementById('url-success');
        
        // Initially hide feedback
        feedback.classList.add('hidden');
        errorDiv.classList.add('hidden');
        successDiv.classList.add('hidden');
    }
    
    /**
     * Validate URL format and supported platforms
     */
    validateURL() {
        const urlInput = document.getElementById('video-url');
        const url = urlInput.value.trim();
        const feedback = document.getElementById('url-feedback');
        const errorDiv = document.getElementById('url-error');
        const successDiv = document.getElementById('url-success');
        const errorMessage = document.getElementById('url-error-message');
        const successMessage = document.getElementById('url-success-message');
        const statusIcon = document.getElementById('url-status-icon');
        
        if (!url) {
            feedback.classList.add('hidden');
            statusIcon.classList.add('hidden');
            return false;
        }
        
        // Show feedback section
        feedback.classList.remove('hidden');
        
        // Basic URL validation
        try {
            new URL(url);
        } catch {
            this.showURLError('Please enter a valid URL');
            return false;
        }
        
        // Platform validation
        const supportedPlatforms = [
            { name: 'YouTube', pattern: /(youtube\.com|youtu\.be)/ },
            { name: 'TikTok', pattern: /tiktok\.com/ },
            { name: 'Instagram', pattern: /instagram\.com/ },
            { name: 'Facebook', pattern: /facebook\.com/ },
            { name: 'Twitter/X', pattern: /(twitter\.com|x\.com)/ },
            { name: 'Reddit', pattern: /reddit\.com/ },
            { name: 'Vimeo', pattern: /vimeo\.com/ },
            { name: 'Direct Video', pattern: /\.(mp4|avi|mov|mkv|webm|flv)(\?|$)/ }
        ];
        
        const platform = supportedPlatforms.find(p => p.pattern.test(url));
        
        if (!platform) {
            this.showURLError('Platform not supported. Please use YouTube, TikTok, Instagram, Facebook, Twitter/X, Reddit, Vimeo, or direct video links.');
            return false;
        }
        
        // Show success
        this.showURLSuccess(`${platform.name} URL detected`);
        return true;
    }
    
    /**
     * Show URL validation error
     */
    showURLError(message) {
        const errorDiv = document.getElementById('url-error');
        const successDiv = document.getElementById('url-success');
        const errorMessage = document.getElementById('url-error-message');
        const statusIcon = document.getElementById('url-status-icon');
        
        errorMessage.textContent = message;
        errorDiv.classList.remove('hidden');
        successDiv.classList.add('hidden');
        statusIcon.classList.add('hidden');
    }
    
    /**
     * Show URL validation success
     */
    showURLSuccess(message) {
        const errorDiv = document.getElementById('url-error');
        const successDiv = document.getElementById('url-success');
        const successMessage = document.getElementById('url-success-message');
        const statusIcon = document.getElementById('url-status-icon');
        
        successMessage.textContent = message;
        successDiv.classList.remove('hidden');
        errorDiv.classList.add('hidden');
        statusIcon.classList.remove('hidden');
        statusIcon.classList.remove('text-gray-400');
        statusIcon.classList.add('text-green-500');
    }
    
    /**
     * Handle URL form submission
     */
    async handleURLSubmission(event) {
        event.preventDefault();
        
        const urlInput = document.getElementById('video-url');
        const url = urlInput.value.trim();
        
        if (!this.validateURL()) {
            return;
        }
        
        this.currentRequest = { url, type: 'metadata' };
        
        // Track URL submission
        this.analytics.trackEvent('url_submitted', {
            platform: this.detectPlatformFromURL(url),
            url_length: url.length
        });
        
        await this.fetchVideoMetadata(url);
    }
    
    /**
     * Fetch video metadata from API
     */
    async fetchVideoMetadata(url) {
        this.setLoadingState(true);
        this.hideAllSections();
        
        try {
            const response = await fetch(`${this.apiBase}/metadata`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Failed to fetch video metadata');
            }
            
            const metadata = await response.json();
            
            // Track successful metadata fetch
            this.analytics.trackEvent('metadata_fetched', {
                platform: metadata.platform,
                duration: metadata.duration,
                qualities_available: metadata.available_qualities.length,
                audio_available: metadata.audio_available
            });
            
            this.displayVideoMetadata(metadata);
            
            // Show strategic ads after metadata is displayed
            this.adManager.showStrategicAds();
            
        } catch (error) {
            console.error('Metadata fetch error:', error);
            this.showError(error.message, [
                'Check if the URL is correct and accessible',
                'Make sure the video is public and not private',
                'Try refreshing the page and trying again'
            ]);
        } finally {
            this.setLoadingState(false);
        }
    }
    
    /**
     * Display video metadata in the UI
     */
    displayVideoMetadata(metadata) {
        // Show metadata section
        const metadataSection = document.getElementById('metadata-section');
        metadataSection.classList.remove('hidden');
        
        // Update video information
        document.getElementById('video-thumbnail').src = metadata.thumbnail;
        document.getElementById('video-thumbnail').alt = metadata.title;
        document.getElementById('video-title').textContent = metadata.title;
        
        // Update duration
        const durationSpan = document.querySelector('#video-duration span');
        durationSpan.textContent = this.formatDuration(metadata.duration);
        
        // Update platform
        const platformSpan = document.querySelector('#video-platform span');
        platformSpan.textContent = metadata.platform.charAt(0).toUpperCase() + metadata.platform.slice(1);
        
        // Display video quality options
        this.displayVideoQualities(metadata.available_qualities, metadata.original_url);
        
        // Display audio options if available
        if (metadata.audio_available) {
            this.displayAudioOptions(metadata.original_url);
        } else {
            document.getElementById('audio-section').style.display = 'none';
        }
        
        // Add premium feature hints
        setTimeout(() => {
            this.adManager.addPremiumHints();
        }, 1000);
    }
    
    /**
     * Display video quality options
     */
    displayVideoQualities(qualities, url) {
        const container = document.getElementById('video-qualities');
        container.innerHTML = '';
        
        qualities.forEach(quality => {
            const qualityDiv = document.createElement('div');
            qualityDiv.className = 'flex items-center justify-between p-3 border border-gray-200 rounded-lg hover:border-primary-300 transition-colors';
            
            qualityDiv.innerHTML = `
                <div class="flex items-center space-x-3">
                    <div class="flex-shrink-0">
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            ${quality.quality}
                        </span>
                    </div>
                    <div>
                        <p class="text-sm font-medium text-gray-900">${quality.format.toUpperCase()} • ${quality.quality}</p>
                        <p class="text-xs text-gray-500">${quality.filesize ? this.formatFileSize(quality.filesize) : 'Size unknown'}</p>
                    </div>
                </div>
                <button 
                    class="download-video-btn bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                    data-url="${url}" 
                    data-quality="${quality.quality}"
                    data-format="${quality.format}"
                >
                    Download
                </button>
            `;
            
            // Bind download event
            const downloadBtn = qualityDiv.querySelector('.download-video-btn');
            downloadBtn.addEventListener('click', () => this.initiateVideoDownload(url, quality.quality, quality.format));
            
            container.appendChild(qualityDiv);
        });
    }
    
    /**
     * Display audio extraction options
     */
    displayAudioOptions(url) {
        const container = document.getElementById('audio-qualities');
        container.innerHTML = '';
        
        const audioQualities = [
            { quality: '128kbps', bitrate: 128 },
            { quality: '320kbps', bitrate: 320 }
        ];
        
        audioQualities.forEach(audio => {
            const audioDiv = document.createElement('div');
            audioDiv.className = 'flex items-center justify-between p-3 border border-gray-200 rounded-lg hover:border-primary-300 transition-colors';
            
            audioDiv.innerHTML = `
                <div class="flex items-center space-x-3">
                    <div class="flex-shrink-0">
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            MP3
                        </span>
                    </div>
                    <div>
                        <p class="text-sm font-medium text-gray-900">MP3 Audio • ${audio.quality}</p>
                        <p class="text-xs text-gray-500">Audio only extraction</p>
                    </div>
                </div>
                <button 
                    class="extract-audio-btn bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                    data-url="${url}" 
                    data-quality="${audio.quality}"
                >
                    Extract Audio
                </button>
            `;
            
            // Bind audio extraction event
            const extractBtn = audioDiv.querySelector('.extract-audio-btn');
            extractBtn.addEventListener('click', () => this.initiateAudioExtraction(url, audio.quality));
            
            container.appendChild(audioDiv);
        });
    }
    
    /**
     * Initiate video download
     */
    async initiateVideoDownload(url, quality, format) {
        this.currentRequest = { url, quality, format, type: 'video' };
        this.downloadStartTime = Date.now();
        
        // Track download initiation
        const platform = this.detectPlatformFromURL(url);
        this.analytics.trackDownload(platform, quality, format, 'video');
        
        try {
            const response = await fetch(`${this.apiBase}/download`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url, quality, format })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Failed to start download');
            }
            
            const result = await response.json();
            this.currentTaskId = result.task_id;
            
            this.showProgressSection();
            
            // Show rewarded video ad for faster processing
            setTimeout(async () => {
                const watchedAd = await this.adManager.showRewardedVideoAd();
                if (watchedAd) {
                    // User watched ad, apply priority processing
                    this.updateProgress(25, 'Priority processing activated...');
                }
            }, 3000);
            
            this.startProgressTracking();
            
        } catch (error) {
            console.error('Download initiation error:', error);
            this.showError(error.message, [
                'Check your internet connection',
                'Verify the video is still available',
                'Try selecting a different quality option'
            ]);
        }
    }
    
    /**
     * Initiate audio extraction
     */
    async initiateAudioExtraction(url, quality) {
        this.currentRequest = { url, quality, type: 'audio' };
        this.downloadStartTime = Date.now();
        
        // Track audio extraction initiation
        const platform = this.detectPlatformFromURL(url);
        this.analytics.trackDownload(platform, quality, 'mp3', 'audio');
        
        try {
            const response = await fetch(`${this.apiBase}/extract-audio`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url, quality })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Failed to start audio extraction');
            }
            
            const result = await response.json();
            this.currentTaskId = result.task_id;
            
            this.showProgressSection();
            
            // Show rewarded video ad for faster processing
            setTimeout(async () => {
                const watchedAd = await this.adManager.showRewardedVideoAd();
                if (watchedAd) {
                    // User watched ad, apply priority processing
                    this.updateProgress(25, 'Priority processing activated...');
                }
            }, 3000);
            
            this.startProgressTracking();
            
        } catch (error) {
            console.error('Audio extraction error:', error);
            this.showError(error.message, [
                'Check if the video contains audio',
                'Verify your internet connection',
                'Try refreshing and starting over'
            ]);
        }
    }
    
    /**
     * Show progress section and hide others
     */
    showProgressSection() {
        this.hideAllSections();
        const progressSection = document.getElementById('progress-section');
        progressSection.classList.remove('hidden');
        
        // Reset progress
        this.updateProgress(0, 'Preparing download...');
        this.updateProgressStep('validate', 'active');
    }
    
    /**
     * Start tracking download progress
     */
    startProgressTracking() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }
        
        this.progressInterval = setInterval(() => {
            this.checkDownloadStatus();
        }, 2000); // Check every 2 seconds
    }
    
    /**
     * Check download status via API
     */
    async checkDownloadStatus() {
        if (!this.currentTaskId) return;
        
        try {
            const response = await fetch(`${this.apiBase}/status/${this.currentTaskId}`);
            
            if (!response.ok) {
                throw new Error('Failed to check download status');
            }
            
            const status = await response.json();
            this.handleStatusUpdate(status);
            
        } catch (error) {
            console.error('Status check error:', error);
            this.stopProgressTracking();
            this.showError('Failed to track download progress', [
                'The download may still be processing',
                'Try refreshing the page in a few minutes'
            ]);
        }
    }
    
    /**
     * Handle status update from API
     */
    handleStatusUpdate(status) {
        switch (status.status) {
            case 'pending':
                this.updateProgress(10, 'Request queued...');
                this.updateProgressStep('validate', 'active');
                break;
                
            case 'processing':
                this.updateProgress(50, 'Processing video...');
                this.updateProgressStep('validate', 'completed');
                this.updateProgressStep('extract', 'active');
                break;
                
            case 'converting':
                this.updateProgress(75, 'Converting file...');
                this.updateProgressStep('extract', 'completed');
                this.updateProgressStep('process', 'active');
                break;
                
            case 'completed':
                this.updateProgress(100, 'Download ready!');
                this.updateProgressStep('process', 'completed');
                this.updateProgressStep('complete', 'completed');
                this.stopProgressTracking();
                
                // Track download completion
                const processingTime = this.downloadStartTime ? Date.now() - this.downloadStartTime : null;
                const platform = this.detectPlatformFromURL(this.currentRequest.url);
                this.analytics.trackDownloadComplete(
                    platform,
                    this.currentRequest.quality,
                    this.currentRequest.format || 'mp3',
                    this.currentRequest.type,
                    processingTime
                );
                
                this.showDownloadComplete(status.download_url);
                break;
                
            case 'failed':
                this.stopProgressTracking();
                
                // Track download failure
                const platform = this.detectPlatformFromURL(this.currentRequest.url);
                this.analytics.trackEvent('download_failed', {
                    platform: platform,
                    quality: this.currentRequest.quality,
                    type: this.currentRequest.type,
                    error_message: status.error_message
                });
                
                this.showError(status.error_message || 'Download failed', [
                    'Try downloading with a different quality',
                    'Check if the video is still available',
                    'Refresh the page and try again'
                ]);
                break;
        }
    }
    
    /**
     * Update progress bar and text
     */
    updateProgress(percentage, text) {
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        const progressPercentage = document.getElementById('progress-percentage');
        
        progressBar.style.width = `${percentage}%`;
        progressText.textContent = text;
        progressPercentage.textContent = `${percentage}%`;
    }
    
    /**
     * Update progress step status
     */
    updateProgressStep(stepName, status) {
        const step = document.getElementById(`step-${stepName}`);
        const circle = step.querySelector('.w-4');
        
        // Remove existing classes
        step.classList.remove('step-active', 'step-completed');
        circle.classList.remove('bg-gray-300', 'bg-blue-500', 'bg-green-500');
        
        if (status === 'active') {
            step.classList.add('step-active');
            circle.classList.add('bg-blue-500');
        } else if (status === 'completed') {
            step.classList.add('step-completed');
            circle.classList.add('bg-green-500');
        } else {
            circle.classList.add('bg-gray-300');
        }
    }
    
    /**
     * Stop progress tracking
     */
    stopProgressTracking() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
    }
    
    /**
     * Show download complete section
     */
    showDownloadComplete(downloadUrl) {
        this.hideAllSections();
        const completeSection = document.getElementById('download-complete-section');
        completeSection.classList.remove('hidden');
        
        // Set download link
        const downloadLink = document.getElementById('download-link');
        downloadLink.href = downloadUrl;
        
        // Start cleanup timer
        this.startCleanupTimer();
    }
    
    /**
     * Start cleanup countdown timer
     */
    startCleanupTimer() {
        let timeLeft = 30 * 60; // 30 minutes in seconds
        const timerElement = document.getElementById('cleanup-timer');
        
        this.cleanupTimer = setInterval(() => {
            const minutes = Math.floor(timeLeft / 60);
            const seconds = timeLeft % 60;
            timerElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            
            timeLeft--;
            
            if (timeLeft < 0) {
                clearInterval(this.cleanupTimer);
                timerElement.textContent = 'File expired';
            }
        }, 1000);
    }
    
    /**
     * Show error section
     */
    showError(message, suggestions = []) {
        this.hideAllSections();
        const errorSection = document.getElementById('error-section');
        errorSection.classList.remove('hidden');
        
        document.getElementById('error-message').textContent = message;
        
        const suggestionsContainer = document.getElementById('error-suggestions');
        suggestionsContainer.innerHTML = '';
        
        suggestions.forEach(suggestion => {
            const suggestionDiv = document.createElement('div');
            suggestionDiv.className = 'flex items-start space-x-2 text-sm text-red-700';
            suggestionDiv.innerHTML = `
                <span class="text-red-500 mt-0.5">•</span>
                <span>${suggestion}</span>
            `;
            suggestionsContainer.appendChild(suggestionDiv);
        });
    }
    
    /**
     * Hide all main sections
     */
    hideAllSections() {
        const sections = [
            'metadata-section',
            'progress-section', 
            'download-complete-section',
            'error-section'
        ];
        
        sections.forEach(sectionId => {
            document.getElementById(sectionId).classList.add('hidden');
        });
    }
    
    /**
     * Set loading state for the form
     */
    setLoadingState(loading) {
        const fetchBtn = document.getElementById('fetch-btn');
        const fetchBtnText = document.getElementById('fetch-btn-text');
        const fetchBtnLoading = document.getElementById('fetch-btn-loading');
        const urlInput = document.getElementById('video-url');
        
        if (loading) {
            fetchBtn.disabled = true;
            fetchBtnText.textContent = 'Processing...';
            fetchBtnLoading.classList.remove('hidden');
            urlInput.disabled = true;
        } else {
            fetchBtn.disabled = false;
            fetchBtnText.textContent = 'Get Video Info';
            fetchBtnLoading.classList.add('hidden');
            urlInput.disabled = false;
        }
    }
    
    /**
     * Retry the last request
     */
    async retryLastRequest() {
        if (!this.currentRequest) return;
        
        if (this.currentRequest.type === 'metadata') {
            await this.fetchVideoMetadata(this.currentRequest.url);
        } else if (this.currentRequest.type === 'video') {
            await this.initiateVideoDownload(
                this.currentRequest.url, 
                this.currentRequest.quality, 
                this.currentRequest.format
            );
        } else if (this.currentRequest.type === 'audio') {
            await this.initiateAudioExtraction(
                this.currentRequest.url, 
                this.currentRequest.quality
            );
        }
    }
    
    /**
     * Reset UI to initial state
     */
    resetUI() {
        // Clear form
        document.getElementById('video-url').value = '';
        
        // Hide all sections
        this.hideAllSections();
        
        // Reset validation
        document.getElementById('url-feedback').classList.add('hidden');
        
        // Clear timers
        this.stopProgressTracking();
        if (this.cleanupTimer) {
            clearInterval(this.cleanupTimer);
            this.cleanupTimer = null;
        }
        
        // Reset state
        this.currentRequest = null;
        this.currentTaskId = null;
        
        // Focus URL input
        document.getElementById('video-url').focus();
    }
    
    /**
     * Format duration from seconds to MM:SS or HH:MM:SS
     */
    formatDuration(seconds) {
        if (!seconds) return '0:00';
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        }
    }
    
    /**
     * Format file size in human readable format
     */
    formatFileSize(bytes) {
        if (!bytes) return 'Unknown size';
        
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        
        return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
    }
    
    /**
     * Detect platform from URL
     */
    detectPlatformFromURL(url) {
        const platformPatterns = {
            'youtube': /(youtube\.com|youtu\.be)/,
            'tiktok': /tiktok\.com/,
            'instagram': /instagram\.com/,
            'facebook': /facebook\.com/,
            'twitter': /(twitter\.com|x\.com)/,
            'reddit': /reddit\.com/,
            'vimeo': /vimeo\.com/,
            'direct': /\.(mp4|avi|mov|mkv|webm|flv)(\?|$)/
        };
        
        for (const [platform, pattern] of Object.entries(platformPatterns)) {
            if (pattern.test(url)) {
                return platform;
            }
        }
        
        return 'unknown';
    }
    
    /**
     * Add privacy settings link to footer
     */
    addPrivacySettingsLink() {
        const footer = document.querySelector('footer .border-t');
        if (footer) {
            const privacyLink = document.createElement('div');
            privacyLink.className = 'mt-4 text-center';
            privacyLink.innerHTML = `
                <a href="#" id="privacy-settings-link" class="text-sm text-gray-500 hover:text-gray-700 underline">
                    Privacy Settings
                </a>
            `;
            footer.appendChild(privacyLink);
        }
    }
}

// Initialize VidNet UI when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.vidnetUI = new VidNetUI();
    window.adManager = window.vidnetUI.adManager;
    
    // Send ad performance data periodically
    setInterval(() => {
        if (window.adManager) {
            window.adManager.sendPerformanceData();
        }
    }, 60000); // Every minute
});

// Export for Node.js usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VidNetUI;
}

// Make globally available for browser testing
if (typeof window !== 'undefined') {
    window.VidNetUI = VidNetUI;
}