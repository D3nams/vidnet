/**
 * Analytics Manager
 * Handles Google Analytics 4, Facebook Pixel, and custom metrics collection
 * with GDPR/CCPA compliance
 */
class AnalyticsManager {
    constructor() {
        this.isInitialized = false;
        this.consentGiven = false;
        this.customMetrics = {
            downloads_total: 0,
            downloads_by_platform: {},
            downloads_by_quality: {},
            page_views: 0,
            session_start: Date.now(),
            user_agent: navigator.userAgent,
            session_id: this.generateSessionId()
        };
        
        // Configuration
        this.config = {
            ga4_measurement_id: 'G-XXXXXXXXXX', // Replace with actual GA4 ID
            facebook_pixel_id: '1234567890123456', // Replace with actual Pixel ID
            debug_mode: window.location.hostname === 'localhost'
        };
        
        this.init();
    }
    
    /**
     * Initialize analytics system
     */
    init() {
        console.log('Analytics Manager initializing...');
        
        // Check for existing consent
        this.checkExistingConsent();
        
        // Show consent banner if needed
        if (!this.consentGiven && !this.hasConsentDecision()) {
            this.showConsentBanner();
        } else if (this.consentGiven) {
            this.initializeTracking();
        }
        
        // Track page view
        this.trackPageView();
        
        this.isInitialized = true;
        console.log('Analytics Manager initialized');
    }
    
    /**
     * Check for existing consent from localStorage
     */
    checkExistingConsent() {
        const consent = localStorage.getItem('vidnet_analytics_consent');
        if (consent === 'accepted') {
            this.consentGiven = true;
        }
    }
    
    /**
     * Check if user has made a consent decision
     */
    hasConsentDecision() {
        return localStorage.getItem('vidnet_analytics_consent') !== null;
    }
    
    /**
     * Show GDPR/CCPA consent banner
     */
    showConsentBanner() {
        const banner = document.createElement('div');
        banner.id = 'consent-banner';
        banner.className = 'fixed bottom-0 left-0 right-0 bg-gray-900 text-white p-4 shadow-lg z-50 transform translate-y-full transition-transform duration-300';
        
        banner.innerHTML = `
            <div class="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between space-y-3 sm:space-y-0 sm:space-x-4">
                <div class="flex-1 text-sm">
                    <p class="mb-2">
                        <strong>🍪 We value your privacy</strong>
                    </p>
                    <p class="text-gray-300">
                        We use cookies and analytics to improve your experience and measure our performance. 
                        Your data helps us optimize our service and provide better downloads.
                    </p>
                </div>
                <div class="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-3">
                    <button 
                        id="consent-decline" 
                        class="px-4 py-2 text-sm border border-gray-600 rounded-lg hover:bg-gray-800 transition-colors"
                    >
                        Decline
                    </button>
                    <button 
                        id="consent-accept" 
                        class="px-4 py-2 text-sm bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors"
                    >
                        Accept All
                    </button>
                    <button 
                        id="consent-settings" 
                        class="px-4 py-2 text-sm text-gray-300 hover:text-white transition-colors underline"
                    >
                        Settings
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(banner);
        
        // Animate in
        setTimeout(() => {
            banner.classList.remove('translate-y-full');
        }, 100);
        
        // Bind events
        document.getElementById('consent-accept').addEventListener('click', () => this.acceptConsent());
        document.getElementById('consent-decline').addEventListener('click', () => this.declineConsent());
        document.getElementById('consent-settings').addEventListener('click', () => this.showConsentSettings());
    }
    
    /**
     * Show detailed consent settings modal
     */
    showConsentSettings() {
        const modal = document.createElement('div');
        modal.id = 'consent-modal';
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4';
        
        modal.innerHTML = `
            <div class="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                <div class="p-6">
                    <div class="flex items-center justify-between mb-6">
                        <h2 class="text-xl font-semibold text-gray-900">Privacy Settings</h2>
                        <button id="close-consent-modal" class="text-gray-400 hover:text-gray-600">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>
                    
                    <div class="space-y-6">
                        <div>
                            <h3 class="font-medium text-gray-900 mb-2">Essential Cookies</h3>
                            <p class="text-sm text-gray-600 mb-3">
                                Required for basic site functionality. These cannot be disabled.
                            </p>
                            <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                                <span class="text-sm font-medium">Always Active</span>
                                <div class="w-12 h-6 bg-green-500 rounded-full flex items-center justify-end px-1">
                                    <div class="w-4 h-4 bg-white rounded-full"></div>
                                </div>
                            </div>
                        </div>
                        
                        <div>
                            <h3 class="font-medium text-gray-900 mb-2">Analytics & Performance</h3>
                            <p class="text-sm text-gray-600 mb-3">
                                Help us understand how you use our service to improve performance and user experience.
                            </p>
                            <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                                <div>
                                    <div class="text-sm font-medium">Google Analytics</div>
                                    <div class="text-xs text-gray-500">Usage statistics and performance metrics</div>
                                </div>
                                <label class="relative inline-flex items-center cursor-pointer">
                                    <input type="checkbox" id="analytics-toggle" class="sr-only peer" checked>
                                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                                </label>
                            </div>
                        </div>
                        
                        <div>
                            <h3 class="font-medium text-gray-900 mb-2">Marketing & Advertising</h3>
                            <p class="text-sm text-gray-600 mb-3">
                                Used to track conversions and optimize our advertising efforts.
                            </p>
                            <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                                <div>
                                    <div class="text-sm font-medium">Facebook Pixel</div>
                                    <div class="text-xs text-gray-500">Conversion tracking and ad optimization</div>
                                </div>
                                <label class="relative inline-flex items-center cursor-pointer">
                                    <input type="checkbox" id="marketing-toggle" class="sr-only peer" checked>
                                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                                </label>
                            </div>
                        </div>
                        
                        <div class="border-t pt-4">
                            <h3 class="font-medium text-gray-900 mb-2">Your Rights</h3>
                            <div class="text-sm text-gray-600 space-y-2">
                                <p>• You can change these settings at any time</p>
                                <p>• We never sell your personal data</p>
                                <p>• Data is processed securely and anonymously when possible</p>
                                <p>• You can request data deletion by contacting us</p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="flex flex-col sm:flex-row space-y-3 sm:space-y-0 sm:space-x-3 mt-8">
                        <button 
                            id="save-consent-settings" 
                            class="flex-1 bg-primary-600 hover:bg-primary-700 text-white py-3 px-6 rounded-lg font-medium transition-colors"
                        >
                            Save Settings
                        </button>
                        <button 
                            id="accept-all-modal" 
                            class="flex-1 border border-gray-300 hover:bg-gray-50 text-gray-700 py-3 px-6 rounded-lg font-medium transition-colors"
                        >
                            Accept All
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Bind events
        document.getElementById('close-consent-modal').addEventListener('click', () => this.closeConsentModal());
        document.getElementById('save-consent-settings').addEventListener('click', () => this.saveConsentSettings());
        document.getElementById('accept-all-modal').addEventListener('click', () => {
            this.closeConsentModal();
            this.acceptConsent();
        });
        
        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeConsentModal();
            }
        });
    }
    
    /**
     * Close consent modal
     */
    closeConsentModal() {
        const modal = document.getElementById('consent-modal');
        if (modal) {
            modal.remove();
        }
    }
    
    /**
     * Save consent settings from modal
     */
    saveConsentSettings() {
        const analyticsEnabled = document.getElementById('analytics-toggle').checked;
        const marketingEnabled = document.getElementById('marketing-toggle').checked;
        
        const consentData = {
            analytics: analyticsEnabled,
            marketing: marketingEnabled,
            timestamp: Date.now()
        };
        
        localStorage.setItem('vidnet_analytics_consent', 'custom');
        localStorage.setItem('vidnet_consent_settings', JSON.stringify(consentData));
        
        this.consentGiven = analyticsEnabled || marketingEnabled;
        
        if (this.consentGiven) {
            this.initializeTracking(consentData);
        }
        
        // Send consent to backend
        this.sendConsentToBackend(consentData);
        
        this.closeConsentModal();
        this.hideConsentBanner();
        
        this.trackEvent('consent_configured', {
            analytics_enabled: analyticsEnabled,
            marketing_enabled: marketingEnabled
        });
    }
    
    /**
     * Accept all consent
     */
    acceptConsent() {
        const consentData = {
            analytics: true,
            marketing: true,
            timestamp: Date.now()
        };
        
        localStorage.setItem('vidnet_analytics_consent', 'accepted');
        localStorage.setItem('vidnet_consent_settings', JSON.stringify(consentData));
        
        this.consentGiven = true;
        this.initializeTracking();
        this.hideConsentBanner();
        
        // Send consent to backend
        this.sendConsentToBackend(consentData);
        
        this.trackEvent('consent_accepted', {
            method: 'accept_all'
        });
    }
    
    /**
     * Decline consent
     */
    declineConsent() {
        localStorage.setItem('vidnet_analytics_consent', 'declined');
        this.consentGiven = false;
        this.hideConsentBanner();
        
        // Only track essential metrics
        this.trackEvent('consent_declined', {
            method: 'decline_all'
        });
    }
    
    /**
     * Hide consent banner
     */
    hideConsentBanner() {
        const banner = document.getElementById('consent-banner');
        if (banner) {
            banner.classList.add('translate-y-full');
            setTimeout(() => banner.remove(), 300);
        }
    }
    
    /**
     * Initialize tracking services based on consent
     */
    initializeTracking(customSettings = null) {
        const settings = customSettings || JSON.parse(localStorage.getItem('vidnet_consent_settings') || '{"analytics": true, "marketing": true}');
        
        if (settings.analytics) {
            this.initializeGoogleAnalytics();
        }
        
        if (settings.marketing) {
            this.initializeFacebookPixel();
        }
        
        console.log('Tracking initialized with settings:', settings);
    }
    
    /**
     * Initialize Google Analytics 4
     */
    initializeGoogleAnalytics() {
        // Load gtag script
        const script = document.createElement('script');
        script.async = true;
        script.src = `https://www.googletagmanager.com/gtag/js?id=${this.config.ga4_measurement_id}`;
        document.head.appendChild(script);
        
        // Initialize gtag
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        window.gtag = gtag;
        
        gtag('js', new Date());
        gtag('config', this.config.ga4_measurement_id, {
            debug_mode: this.config.debug_mode,
            anonymize_ip: true,
            allow_google_signals: false,
            allow_ad_personalization_signals: false
        });
        
        console.log('Google Analytics 4 initialized');
    }
    
    /**
     * Initialize Facebook Pixel
     */
    initializeFacebookPixel() {
        // Facebook Pixel code
        !function(f,b,e,v,n,t,s)
        {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
        n.callMethod.apply(n,arguments):n.queue.push(arguments)};
        if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
        n.queue=[];t=b.createElement(e);t.async=!0;
        t.src=v;s=b.getElementsByTagName(e)[0];
        s.parentNode.insertBefore(t,s)}(window, document,'script',
        'https://connect.facebook.net/en_US/fbevents.js');
        
        fbq('init', this.config.facebook_pixel_id);
        fbq('track', 'PageView');
        
        console.log('Facebook Pixel initialized');
    }
    
    /**
     * Generate unique session ID
     */
    generateSessionId() {
        return 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    /**
     * Track page view
     */
    trackPageView() {
        this.customMetrics.page_views++;
        
        const pageData = {
            page_title: document.title,
            page_location: window.location.href,
            page_path: window.location.pathname,
            session_id: this.customMetrics.session_id,
            timestamp: Date.now()
        };
        
        // Track in custom metrics
        this.storeCustomMetric('page_view', pageData);
        
        // Track in GA4 if consent given
        if (this.consentGiven && window.gtag) {
            gtag('event', 'page_view', pageData);
        }
        
        // Track in Facebook Pixel if consent given
        if (this.consentGiven && window.fbq) {
            fbq('track', 'PageView');
        }
        
        console.log('Page view tracked:', pageData);
    }
    
    /**
     * Track download events
     */
    trackDownload(platform, quality, format, type = 'video') {
        this.customMetrics.downloads_total++;
        
        // Update platform stats
        if (!this.customMetrics.downloads_by_platform[platform]) {
            this.customMetrics.downloads_by_platform[platform] = 0;
        }
        this.customMetrics.downloads_by_platform[platform]++;
        
        // Update quality stats
        if (!this.customMetrics.downloads_by_quality[quality]) {
            this.customMetrics.downloads_by_quality[quality] = 0;
        }
        this.customMetrics.downloads_by_quality[quality]++;
        
        const downloadData = {
            platform: platform,
            quality: quality,
            format: format,
            type: type, // 'video' or 'audio'
            session_id: this.customMetrics.session_id,
            timestamp: Date.now()
        };
        
        // Store custom metric
        this.storeCustomMetric('download_start', downloadData);
        
        // Track in GA4 if consent given
        if (this.consentGiven && window.gtag) {
            gtag('event', 'download_start', {
                event_category: 'engagement',
                event_label: `${platform}_${quality}_${type}`,
                custom_parameter_1: platform,
                custom_parameter_2: quality,
                custom_parameter_3: type
            });
        }
        
        // Track in Facebook Pixel if consent given
        if (this.consentGiven && window.fbq) {
            fbq('track', 'InitiateCheckout', {
                content_type: type,
                content_category: platform,
                value: 1,
                currency: 'USD'
            });
        }
        
        console.log('Download tracked:', downloadData);
    }
    
    /**
     * Track download completion
     */
    trackDownloadComplete(platform, quality, format, type = 'video', processingTime = null) {
        const completionData = {
            platform: platform,
            quality: quality,
            format: format,
            type: type,
            processing_time: processingTime,
            session_id: this.customMetrics.session_id,
            timestamp: Date.now()
        };
        
        // Store custom metric
        this.storeCustomMetric('download_complete', completionData);
        
        // Track in GA4 if consent given
        if (this.consentGiven && window.gtag) {
            gtag('event', 'download_complete', {
                event_category: 'conversion',
                event_label: `${platform}_${quality}_${type}`,
                value: 1,
                custom_parameter_1: platform,
                custom_parameter_2: quality,
                custom_parameter_3: type
            });
            
            if (processingTime) {
                gtag('event', 'timing_complete', {
                    name: 'download_processing',
                    value: processingTime
                });
            }
        }
        
        // Track in Facebook Pixel if consent given
        if (this.consentGiven && window.fbq) {
            fbq('track', 'Purchase', {
                content_type: type,
                content_category: platform,
                value: 1,
                currency: 'USD'
            });
        }
        
        console.log('Download completion tracked:', completionData);
    }
    
    /**
     * Track custom events
     */
    trackEvent(eventName, eventData = {}) {
        const fullEventData = {
            ...eventData,
            session_id: this.customMetrics.session_id,
            timestamp: Date.now()
        };
        
        // Store custom metric
        this.storeCustomMetric(eventName, fullEventData);
        
        // Track in GA4 if consent given
        if (this.consentGiven && window.gtag) {
            gtag('event', eventName, {
                event_category: 'custom',
                ...eventData
            });
        }
        
        console.log(`Custom event tracked: ${eventName}`, fullEventData);
    }
    
    /**
     * Store custom metrics in localStorage and send to backend
     */
    storeCustomMetric(eventType, data) {
        const eventData = {
            event_type: eventType,
            data: data,
            timestamp: Date.now(),
            session_id: this.customMetrics.session_id,
            user_agent: navigator.userAgent
        };
        
        // Store locally
        const metrics = JSON.parse(localStorage.getItem('vidnet_custom_metrics') || '[]');
        metrics.push(eventData);
        
        // Keep only last 100 events to prevent storage bloat
        if (metrics.length > 100) {
            metrics.splice(0, metrics.length - 100);
        }
        
        localStorage.setItem('vidnet_custom_metrics', JSON.stringify(metrics));
        localStorage.setItem('vidnet_session_metrics', JSON.stringify(this.customMetrics));
        
        // Send to backend if consent given
        if (this.consentGiven) {
            this.sendEventToBackend(eventData);
        }
    }
    
    /**
     * Send analytics event to backend
     */
    async sendEventToBackend(eventData) {
        try {
            const response = await fetch('/api/v1/analytics/events', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Client-ID': this.customMetrics.session_id
                },
                body: JSON.stringify({
                    events: [eventData],
                    client_id: this.customMetrics.session_id
                })
            });
            
            if (!response.ok) {
                console.warn('Failed to send analytics event to backend:', response.status);
            }
        } catch (error) {
            console.warn('Failed to send analytics event to backend:', error);
        }
    }
    
    /**
     * Send consent data to backend
     */
    async sendConsentToBackend(consentData) {
        try {
            const response = await fetch('/api/v1/analytics/consent', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Client-ID': this.customMetrics.session_id
                },
                body: JSON.stringify(consentData)
            });
            
            if (!response.ok) {
                console.warn('Failed to send consent data to backend:', response.status);
            }
        } catch (error) {
            console.warn('Failed to send consent data to backend:', error);
        }
    }
    
    /**
     * Get analytics dashboard data
     */
    getDashboardData() {
        const storedMetrics = JSON.parse(localStorage.getItem('vidnet_custom_metrics') || '[]');
        const sessionMetrics = JSON.parse(localStorage.getItem('vidnet_session_metrics') || '{}');
        
        return {
            session: this.customMetrics,
            stored: sessionMetrics,
            events: storedMetrics,
            consent_status: localStorage.getItem('vidnet_analytics_consent'),
            consent_settings: JSON.parse(localStorage.getItem('vidnet_consent_settings') || '{}')
        };
    }
    
    /**
     * Clear all analytics data (for privacy compliance)
     */
    clearAllData() {
        localStorage.removeItem('vidnet_custom_metrics');
        localStorage.removeItem('vidnet_session_metrics');
        localStorage.removeItem('vidnet_analytics_consent');
        localStorage.removeItem('vidnet_consent_settings');
        
        this.customMetrics = {
            downloads_total: 0,
            downloads_by_platform: {},
            downloads_by_quality: {},
            page_views: 0,
            session_start: Date.now(),
            user_agent: navigator.userAgent,
            session_id: this.generateSessionId()
        };
        
        console.log('All analytics data cleared');
    }
    
    /**
     * Show privacy settings (can be called from UI)
     */
    showPrivacySettings() {
        this.showConsentSettings();
    }
}

// Export for Node.js usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AnalyticsManager;
}

// Make globally available for browser usage
if (typeof window !== 'undefined') {
    window.AnalyticsManager = AnalyticsManager;
}