/**
 * Ad Manager
 * Handles strategic ad placement, rewarded video ads, and performance tracking
 * Integrates with Google AdSense, Facebook Audience Network, and custom ad networks
 */
class AdManager {
    constructor(analyticsManager) {
        this.analytics = analyticsManager;
        this.isInitialized = false;
        this.adSlots = new Map();
        this.rewardedAdQueue = [];
        this.currentRewardedAd = null;
        this.adPerformance = {
            impressions: 0,
            clicks: 0,
            revenue: 0,
            ctr: 0,
            slots: {}
        };
        
        // Configuration
        this.config = {
            google_adsense_client: 'ca-pub-XXXXXXXXXX', // Replace with actual AdSense client ID
            facebook_placement_id: 'XXXXXXXXXX_XXXXXXXXXX', // Replace with actual FB placement ID
            rewarded_ad_provider: 'google', // 'google', 'facebook', or 'custom'
            ad_refresh_interval: 30000, // 30 seconds
            max_ads_per_session: 10,
            debug_mode: window.location.hostname === 'localhost'
        };
        
        this.adsShownThisSession = 0;
        this.lastAdRefresh = Date.now();
        
        this.init();
    }
    
    /**
     * Initialize ad manager
     */
    init() {
        console.log('Ad Manager initializing...');
        
        // Wait for analytics consent before showing ads
        if (this.analytics && this.analytics.consentGiven) {
            this.initializeAdNetworks();
        } else {
            // Listen for consent changes
            document.addEventListener('analytics-consent-changed', () => {
                if (this.analytics.consentGiven) {
                    this.initializeAdNetworks();
                }
            });
        }
        
        this.createAdSlots();
        this.setupAdRefreshTimer();
        this.isInitialized = true;
        
        console.log('Ad Manager initialized');
    }
    
    /**
     * Initialize ad networks (Google AdSense, Facebook Audience Network)
     */
    initializeAdNetworks() {
        if (this.config.debug_mode) {
            console.log('Debug mode: Using mock ads');
            this.initializeMockAds();
            return;
        }
        
        this.initializeGoogleAdSense();
        this.initializeFacebookAudienceNetwork();
    }
    
    /**
     * Initialize Google AdSense
     */
    initializeGoogleAdSense() {
        // Load AdSense script
        const script = document.createElement('script');
        script.async = true;
        script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${this.config.google_adsense_client}`;
        script.crossOrigin = 'anonymous';
        document.head.appendChild(script);
        
        // Initialize AdSense
        window.adsbygoogle = window.adsbygoogle || [];
        
        console.log('Google AdSense initialized');
    }
    
    /**
     * Initialize Facebook Audience Network
     */
    initializeFacebookAudienceNetwork() {
        // Load Facebook Audience Network SDK
        window.fbAsyncInit = function() {
            FB.init({
                appId: 'YOUR_APP_ID', // Replace with actual app ID
                xfbml: true,
                version: 'v18.0'
            });
        };
        
        const script = document.createElement('script');
        script.async = true;
        script.defer = true;
        script.crossOrigin = 'anonymous';
        script.src = 'https://connect.facebook.net/en_US/sdk.js';
        document.head.appendChild(script);
        
        console.log('Facebook Audience Network initialized');
    }
    
    /**
     * Initialize mock ads for development/testing
     */
    initializeMockAds() {
        console.log('Mock ads initialized for development');
    }
    
    /**
     * Create ad slots in the UI
     */
    createAdSlots() {
        this.createHeaderBannerSlot();
        this.createSidebarSlot();
        this.createInContentSlots();
    }
    
    /**
     * Create header banner ad slot
     */
    createHeaderBannerSlot() {
        const header = document.querySelector('header');
        if (!header) return;
        
        const adContainer = document.createElement('div');
        adContainer.id = 'header-banner-ad';
        adContainer.className = 'bg-gray-100 border-b border-gray-200 py-2 px-4 text-center hidden';
        adContainer.innerHTML = `
            <div class="max-w-4xl mx-auto">
                <div class="flex items-center justify-between">
                    <div class="flex-1">
                        <div id="header-ad-content" class="min-h-[60px] flex items-center justify-center">
                            <!-- Ad content will be inserted here -->
                        </div>
                    </div>
                    <button id="close-header-ad" class="ml-4 text-gray-400 hover:text-gray-600 text-sm">
                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                        </svg>
                    </button>
                </div>
            </div>
        `;
        
        header.insertAdjacentElement('afterend', adContainer);
        
        // Bind close event
        document.getElementById('close-header-ad').addEventListener('click', () => {
            this.closeAd('header-banner');
        });
        
        this.adSlots.set('header-banner', {
            element: adContainer,
            contentElement: document.getElementById('header-ad-content'),
            type: 'banner',
            size: '728x90',
            visible: false,
            impressions: 0,
            clicks: 0
        });
    }
    
    /**
     * Create sidebar ad slot
     */
    createSidebarSlot() {
        const main = document.querySelector('main');
        if (!main) return;
        
        // Create sidebar container
        const sidebar = document.createElement('div');
        sidebar.id = 'sidebar-ad-container';
        sidebar.className = 'fixed right-4 top-1/2 transform -translate-y-1/2 w-64 z-40 hidden lg:block';
        
        sidebar.innerHTML = `
            <div class="bg-white rounded-lg shadow-lg border border-gray-200 p-4">
                <div class="flex items-center justify-between mb-3">
                    <span class="text-xs text-gray-500 uppercase tracking-wide">Sponsored</span>
                    <button id="close-sidebar-ad" class="text-gray-400 hover:text-gray-600">
                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                        </svg>
                    </button>
                </div>
                <div id="sidebar-ad-content" class="min-h-[250px] flex items-center justify-center">
                    <!-- Ad content will be inserted here -->
                </div>
            </div>
        `;
        
        document.body.appendChild(sidebar);
        
        // Bind close event
        document.getElementById('close-sidebar-ad').addEventListener('click', () => {
            this.closeAd('sidebar');
        });
        
        this.adSlots.set('sidebar', {
            element: sidebar,
            contentElement: document.getElementById('sidebar-ad-content'),
            type: 'rectangle',
            size: '250x250',
            visible: false,
            impressions: 0,
            clicks: 0
        });
    }
    
    /**
     * Create in-content ad slots
     */
    createInContentSlots() {
        // Add ad slot after metadata section
        const metadataSection = document.getElementById('metadata-section');
        if (metadataSection) {
            const inContentAd = document.createElement('div');
            inContentAd.id = 'in-content-ad';
            inContentAd.className = 'bg-gray-50 border border-gray-200 rounded-xl p-6 mb-8 text-center hidden';
            inContentAd.innerHTML = `
                <div class="flex items-center justify-between mb-4">
                    <span class="text-xs text-gray-500 uppercase tracking-wide">Advertisement</span>
                    <button id="close-in-content-ad" class="text-gray-400 hover:text-gray-600">
                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                        </svg>
                    </button>
                </div>
                <div id="in-content-ad-content" class="min-h-[200px] flex items-center justify-center">
                    <!-- Ad content will be inserted here -->
                </div>
            `;
            
            metadataSection.insertAdjacentElement('afterend', inContentAd);
            
            // Bind close event
            document.getElementById('close-in-content-ad').addEventListener('click', () => {
                this.closeAd('in-content');
            });
            
            this.adSlots.set('in-content', {
                element: inContentAd,
                contentElement: document.getElementById('in-content-ad-content'),
                type: 'banner',
                size: '728x200',
                visible: false,
                impressions: 0,
                clicks: 0
            });
        }
    }
    
    /**
     * Show ads strategically based on user interaction
     */
    showStrategicAds() {
        if (!this.analytics.consentGiven || this.adsShownThisSession >= this.config.max_ads_per_session) {
            return;
        }
        
        // Show header banner after URL submission
        setTimeout(() => {
            this.showAd('header-banner', this.createBannerAd());
        }, 2000);
        
        // Show sidebar ad after metadata is displayed
        setTimeout(() => {
            this.showAd('sidebar', this.createSidebarAd());
        }, 5000);
    }
    
    /**
     * Show rewarded video ad during download processing
     */
    async showRewardedVideoAd() {
        if (!this.analytics.consentGiven || this.currentRewardedAd) {
            return false;
        }
        
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.id = 'rewarded-ad-modal';
            modal.className = 'fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50';
            
            modal.innerHTML = `
                <div class="bg-white rounded-xl max-w-md w-full mx-4 p-6 text-center">
                    <div class="mb-4">
                        <div class="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg class="w-8 h-8 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM14.553 7.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z"></path>
                            </svg>
                        </div>
                        <h3 class="text-lg font-semibold text-gray-900 mb-2">Speed up your download!</h3>
                        <p class="text-gray-600 text-sm">Watch a short video to get priority processing and faster downloads.</p>
                    </div>
                    
                    <div id="rewarded-ad-content" class="bg-gray-100 rounded-lg p-8 mb-4 min-h-[200px] flex items-center justify-center">
                        <div class="text-center">
                            <div class="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-2"></div>
                            <p class="text-sm text-gray-600">Loading ad...</p>
                        </div>
                    </div>
                    
                    <div class="flex space-x-3">
                        <button id="skip-rewarded-ad" class="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors">
                            Skip (<span id="skip-countdown">5</span>s)
                        </button>
                        <button id="watch-rewarded-ad" class="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50" disabled>
                            Watch Video
                        </button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            this.currentRewardedAd = modal;
            
            // Simulate ad loading
            setTimeout(() => {
                this.loadRewardedAdContent(modal);
            }, 2000);
            
            // Skip countdown
            let skipCountdown = 5;
            const skipBtn = document.getElementById('skip-rewarded-ad');
            const countdownSpan = document.getElementById('skip-countdown');
            
            const countdownInterval = setInterval(() => {
                skipCountdown--;
                countdownSpan.textContent = skipCountdown;
                
                if (skipCountdown <= 0) {
                    clearInterval(countdownInterval);
                    skipBtn.textContent = 'Skip';
                    skipBtn.disabled = false;
                }
            }, 1000);
            
            // Bind events
            skipBtn.addEventListener('click', () => {
                this.closeRewardedAd(false);
                resolve(false);
            });
            
            document.getElementById('watch-rewarded-ad').addEventListener('click', () => {
                this.playRewardedVideo();
                resolve(true);
            });
            
            // Track impression
            this.trackAdImpression('rewarded-video', 'modal');
        });
    }
    
    /**
     * Load rewarded ad content
     */
    loadRewardedAdContent(modal) {
        const content = modal.querySelector('#rewarded-ad-content');
        const watchBtn = document.getElementById('watch-rewarded-ad');
        
        if (this.config.debug_mode) {
            // Mock ad content for development
            content.innerHTML = `
                <div class="text-center">
                    <div class="w-full h-32 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg flex items-center justify-center mb-3">
                        <div class="text-white">
                            <div class="text-2xl mb-1">🎬</div>
                            <div class="text-sm font-medium">Sample Video Ad</div>
                        </div>
                    </div>
                    <p class="text-xs text-gray-600">This is a demo ad for development</p>
                </div>
            `;
        } else {
            // Load actual ad content from ad network
            content.innerHTML = `
                <div class="text-center">
                    <div class="w-full h-32 bg-gray-200 rounded-lg flex items-center justify-center mb-3">
                        <span class="text-gray-500">Ad Content</span>
                    </div>
                </div>
            `;
        }
        
        watchBtn.disabled = false;
    }
    
    /**
     * Play rewarded video
     */
    playRewardedVideo() {
        const modal = this.currentRewardedAd;
        const content = modal.querySelector('#rewarded-ad-content');
        
        content.innerHTML = `
            <div class="text-center">
                <div class="w-full h-32 bg-black rounded-lg flex items-center justify-center mb-3 relative">
                    <div class="text-white">
                        <div class="animate-pulse">▶️ Playing Video Ad</div>
                    </div>
                    <div class="absolute top-2 right-2 bg-black bg-opacity-50 text-white text-xs px-2 py-1 rounded">
                        <span id="video-timer">0:15</span>
                    </div>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2">
                    <div id="video-progress" class="bg-blue-600 h-2 rounded-full transition-all duration-1000" style="width: 0%"></div>
                </div>
            </div>
        `;
        
        // Simulate video playback
        let progress = 0;
        const duration = 15; // 15 seconds
        const progressBar = document.getElementById('video-progress');
        const timer = document.getElementById('video-timer');
        
        const playbackInterval = setInterval(() => {
            progress++;
            const percentage = (progress / duration) * 100;
            progressBar.style.width = `${percentage}%`;
            
            const remaining = duration - progress;
            timer.textContent = `0:${remaining.toString().padStart(2, '0')}`;
            
            if (progress >= duration) {
                clearInterval(playbackInterval);
                this.completeRewardedAd();
            }
        }, 1000);
        
        // Track ad engagement
        this.trackAdClick('rewarded-video', 'play');
    }
    
    /**
     * Complete rewarded ad and give reward
     */
    completeRewardedAd() {
        const modal = this.currentRewardedAd;
        const content = modal.querySelector('#rewarded-ad-content');
        
        content.innerHTML = `
            <div class="text-center">
                <div class="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
                    <svg class="w-8 h-8 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                    </svg>
                </div>
                <h4 class="font-semibold text-gray-900 mb-2">Reward Earned!</h4>
                <p class="text-sm text-gray-600 mb-4">Your download has been moved to priority queue for faster processing.</p>
                <button id="claim-reward" class="w-full bg-green-600 hover:bg-green-700 text-white py-2 px-4 rounded-lg transition-colors">
                    Continue Download
                </button>
            </div>
        `;
        
        document.getElementById('claim-reward').addEventListener('click', () => {
            this.closeRewardedAd(true);
        });
        
        // Track reward completion
        this.trackAdClick('rewarded-video', 'complete');
        this.analytics.trackEvent('rewarded_ad_completed', {
            reward_type: 'priority_processing'
        });
    }
    
    /**
     * Close rewarded ad
     */
    closeRewardedAd(rewarded = false) {
        if (this.currentRewardedAd) {
            this.currentRewardedAd.remove();
            this.currentRewardedAd = null;
        }
        
        if (rewarded) {
            // Apply reward (priority processing)
            this.analytics.trackEvent('reward_applied', {
                type: 'priority_processing'
            });
        }
    }
    
    /**
     * Show specific ad in slot
     */
    showAd(slotId, adContent) {
        const slot = this.adSlots.get(slotId);
        if (!slot || slot.visible) return;
        
        slot.contentElement.innerHTML = adContent;
        slot.element.classList.remove('hidden');
        slot.visible = true;
        slot.impressions++;
        
        this.adsShownThisSession++;
        this.trackAdImpression(slotId, slot.type);
        
        // Auto-hide after 30 seconds for non-sticky ads
        if (slotId !== 'sidebar') {
            setTimeout(() => {
                this.closeAd(slotId);
            }, 30000);
        }
    }
    
    /**
     * Close specific ad
     */
    closeAd(slotId) {
        const slot = this.adSlots.get(slotId);
        if (!slot || !slot.visible) return;
        
        slot.element.classList.add('hidden');
        slot.visible = false;
        
        this.trackAdClick(slotId, 'close');
    }
    
    /**
     * Create banner ad content
     */
    createBannerAd() {
        if (this.config.debug_mode) {
            return `
                <div class="flex items-center justify-center space-x-4 py-2">
                    <div class="text-sm text-gray-600">
                        <span class="font-medium">🚀 Boost your downloads!</span>
                        Try our premium features for faster processing.
                    </div>
                    <button class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-1 rounded text-sm transition-colors" onclick="window.adManager.trackAdClick('header-banner', 'cta')">
                        Learn More
                    </button>
                </div>
            `;
        }
        
        // Return actual ad network code for production
        return `
            <ins class="adsbygoogle"
                 style="display:inline-block;width:728px;height:90px"
                 data-ad-client="${this.config.google_adsense_client}"
                 data-ad-slot="1234567890"></ins>
            <script>
                (adsbygoogle = window.adsbygoogle || []).push({});
            </script>
        `;
    }
    
    /**
     * Create sidebar ad content
     */
    createSidebarAd() {
        if (this.config.debug_mode) {
            return `
                <div class="text-center">
                    <div class="w-full h-32 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center mb-3">
                        <div class="text-white text-center">
                            <div class="text-2xl mb-1">⚡</div>
                            <div class="text-sm font-medium">Premium Features</div>
                        </div>
                    </div>
                    <h4 class="font-semibold text-gray-900 mb-2">Unlock Premium</h4>
                    <p class="text-xs text-gray-600 mb-3">Get 4K downloads, batch processing, and ad-free experience.</p>
                    <button class="w-full bg-purple-600 hover:bg-purple-700 text-white py-2 px-3 rounded text-sm transition-colors" onclick="window.adManager.trackAdClick('sidebar', 'premium-cta')">
                        Upgrade Now
                    </button>
                </div>
            `;
        }
        
        return `
            <ins class="adsbygoogle"
                 style="display:block"
                 data-ad-client="${this.config.google_adsense_client}"
                 data-ad-slot="0987654321"
                 data-ad-format="auto"></ins>
            <script>
                (adsbygoogle = window.adsbygoogle || []).push({});
            </script>
        `;
    }
    
    /**
     * Add premium feature hints to UI
     */
    addPremiumHints() {
        // Add premium badge to 4K quality options
        const qualityOptions = document.querySelectorAll('[data-quality="4K"], [data-quality="2160p"]');
        qualityOptions.forEach(option => {
            const premiumBadge = document.createElement('span');
            premiumBadge.className = 'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 ml-2';
            premiumBadge.innerHTML = '👑 Premium';
            option.appendChild(premiumBadge);
            
            // Disable the button and add upgrade prompt
            const downloadBtn = option.querySelector('button');
            if (downloadBtn) {
                downloadBtn.disabled = true;
                downloadBtn.textContent = 'Upgrade for 4K';
                downloadBtn.onclick = () => this.showUpgradeModal('4k-quality');
            }
        });
        
        // Add batch download hint
        const metadataSection = document.getElementById('metadata-section');
        if (metadataSection) {
            const batchHint = document.createElement('div');
            batchHint.className = 'mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg';
            batchHint.innerHTML = `
                <div class="flex items-center space-x-2">
                    <svg class="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"></path>
                        <path fill-rule="evenodd" d="M4 5a2 2 0 012-2v1a2 2 0 00-2 2v6a2 2 0 002 2h8a2 2 0 002-2V6a2 2 0 00-2-2V3a2 2 0 012 2v6a2 2 0 01-2 2H6a2 2 0 01-2-2V5z" clip-rule="evenodd"></path>
                    </svg>
                    <div class="flex-1">
                        <p class="text-sm font-medium text-blue-900">💡 Pro Tip</p>
                        <p class="text-xs text-blue-700">Upgrade to Premium for batch downloads, playlist support, and faster processing!</p>
                    </div>
                    <button class="text-blue-600 hover:text-blue-700 text-sm font-medium" onclick="window.adManager.showUpgradeModal('batch-download')">
                        Learn More
                    </button>
                </div>
            `;
            metadataSection.appendChild(batchHint);
        }
    }
    
    /**
     * Show upgrade modal
     */
    showUpgradeModal(feature) {
        const modal = document.createElement('div');
        modal.id = 'upgrade-modal';
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4';
        
        const featureDetails = {
            '4k-quality': {
                title: '4K Ultra HD Downloads',
                description: 'Download videos in stunning 4K resolution with crystal clear quality.',
                features: ['4K/2160p resolution', 'HDR support', 'Premium codecs', 'Faster processing']
            },
            'batch-download': {
                title: 'Batch & Playlist Downloads',
                description: 'Download multiple videos or entire playlists with one click.',
                features: ['Playlist downloads', 'Batch processing', 'Queue management', 'Background downloads']
            }
        };
        
        const details = featureDetails[feature] || featureDetails['4k-quality'];
        
        modal.innerHTML = `
            <div class="bg-white rounded-xl max-w-md w-full">
                <div class="p-6">
                    <div class="text-center mb-6">
                        <div class="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center mx-auto mb-4">
                            <span class="text-2xl">👑</span>
                        </div>
                        <h2 class="text-xl font-semibold text-gray-900 mb-2">${details.title}</h2>
                        <p class="text-gray-600 text-sm">${details.description}</p>
                    </div>
                    
                    <div class="space-y-3 mb-6">
                        ${details.features.map(feature => `
                            <div class="flex items-center space-x-3">
                                <svg class="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                                </svg>
                                <span class="text-sm text-gray-700">${feature}</span>
                            </div>
                        `).join('')}
                    </div>
                    
                    <div class="bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg p-4 text-white text-center mb-6">
                        <div class="text-2xl font-bold mb-1">$4.99/month</div>
                        <div class="text-sm opacity-90">or $39.99/year (save 33%)</div>
                    </div>
                    
                    <div class="space-y-3">
                        <button class="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white py-3 px-6 rounded-lg font-medium transition-colors" onclick="window.adManager.trackUpgradeClick('${feature}', 'monthly')">
                            Start Free Trial
                        </button>
                        <button class="w-full border border-gray-300 hover:bg-gray-50 text-gray-700 py-3 px-6 rounded-lg font-medium transition-colors" onclick="window.adManager.closeUpgradeModal()">
                            Maybe Later
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeUpgradeModal();
            }
        });
        
        // Track modal view
        this.analytics.trackEvent('upgrade_modal_viewed', {
            feature: feature,
            trigger: 'premium_hint'
        });
    }
    
    /**
     * Close upgrade modal
     */
    closeUpgradeModal() {
        const modal = document.getElementById('upgrade-modal');
        if (modal) {
            modal.remove();
        }
    }
    
    /**
     * Track upgrade click
     */
    trackUpgradeClick(feature, plan) {
        this.analytics.trackEvent('upgrade_clicked', {
            feature: feature,
            plan: plan,
            source: 'premium_hint'
        });
        
        // Track conversion in Facebook Pixel
        if (window.fbq) {
            fbq('track', 'Lead', {
                content_name: `Premium ${feature}`,
                value: plan === 'monthly' ? 4.99 : 39.99,
                currency: 'USD'
            });
        }
        
        this.closeUpgradeModal();
        
        // In a real implementation, redirect to payment processor
        alert('Redirecting to payment page...');
    }
    
    /**
     * Track ad impression
     */
    trackAdImpression(slotId, adType) {
        this.adPerformance.impressions++;
        
        if (!this.adPerformance.slots[slotId]) {
            this.adPerformance.slots[slotId] = { impressions: 0, clicks: 0, ctr: 0 };
        }
        this.adPerformance.slots[slotId].impressions++;
        
        // Track in analytics
        this.analytics.trackEvent('ad_impression', {
            slot_id: slotId,
            ad_type: adType,
            session_ads_shown: this.adsShownThisSession
        });
        
        console.log(`Ad impression tracked: ${slotId} (${adType})`);
    }
    
    /**
     * Track ad click
     */
    trackAdClick(slotId, action = 'click') {
        this.adPerformance.clicks++;
        
        if (!this.adPerformance.slots[slotId]) {
            this.adPerformance.slots[slotId] = { impressions: 0, clicks: 0, ctr: 0 };
        }
        this.adPerformance.slots[slotId].clicks++;
        
        // Calculate CTR
        const slot = this.adPerformance.slots[slotId];
        slot.ctr = slot.impressions > 0 ? (slot.clicks / slot.impressions) * 100 : 0;
        this.adPerformance.ctr = this.adPerformance.impressions > 0 ? (this.adPerformance.clicks / this.adPerformance.impressions) * 100 : 0;
        
        // Track in analytics
        this.analytics.trackEvent('ad_click', {
            slot_id: slotId,
            action: action,
            ctr: slot.ctr
        });
        
        // Track in Facebook Pixel for conversion optimization
        if (window.fbq && action === 'cta') {
            fbq('track', 'ViewContent', {
                content_type: 'ad_click',
                content_ids: [slotId]
            });
        }
        
        console.log(`Ad click tracked: ${slotId} (${action}) - CTR: ${slot.ctr.toFixed(2)}%`);
    }
    
    /**
     * Setup ad refresh timer
     */
    setupAdRefreshTimer() {
        setInterval(() => {
            if (Date.now() - this.lastAdRefresh > this.config.ad_refresh_interval) {
                this.refreshAds();
                this.lastAdRefresh = Date.now();
            }
        }, this.config.ad_refresh_interval);
    }
    
    /**
     * Refresh ads in visible slots
     */
    refreshAds() {
        this.adSlots.forEach((slot, slotId) => {
            if (slot.visible && slotId !== 'rewarded-video') {
                // Refresh ad content
                if (slotId === 'header-banner') {
                    slot.contentElement.innerHTML = this.createBannerAd();
                } else if (slotId === 'sidebar') {
                    slot.contentElement.innerHTML = this.createSidebarAd();
                }
                
                this.trackAdImpression(slotId, slot.type + '_refresh');
            }
        });
    }
    
    /**
     * Get ad performance metrics
     */
    getPerformanceMetrics() {
        return {
            ...this.adPerformance,
            session_duration: Date.now() - this.analytics.customMetrics.session_start,
            ads_shown_this_session: this.adsShownThisSession,
            revenue_per_session: this.calculateSessionRevenue()
        };
    }
    
    /**
     * Calculate estimated session revenue
     */
    calculateSessionRevenue() {
        // Rough estimates based on industry averages
        const cpmRate = 2.0; // $2 CPM
        const cpcRate = 0.5; // $0.50 CPC
        
        const impressionRevenue = (this.adPerformance.impressions / 1000) * cpmRate;
        const clickRevenue = this.adPerformance.clicks * cpcRate;
        
        return impressionRevenue + clickRevenue;
    }
    
    /**
     * Send ad performance data to backend
     */
    async sendPerformanceData() {
        if (!this.analytics.consentGiven) return;
        
        try {
            const response = await fetch('/api/v1/analytics/ad-performance', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Client-ID': this.analytics.customMetrics.session_id
                },
                body: JSON.stringify({
                    performance: this.getPerformanceMetrics(),
                    session_id: this.analytics.customMetrics.session_id,
                    timestamp: Date.now()
                })
            });
            
            if (!response.ok) {
                console.warn('Failed to send ad performance data:', response.status);
            }
        } catch (error) {
            console.warn('Failed to send ad performance data:', error);
        }
    }
}

// Export for Node.js usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AdManager;
}

// Make globally available for browser usage
if (typeof window !== 'undefined') {
    window.AdManager = AdManager;
}