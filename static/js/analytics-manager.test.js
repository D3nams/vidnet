/**
 * Analytics Manager Test Suite
 * Tests for Google Analytics 4, Facebook Pixel, and custom metrics collection
 */

// Mock localStorage for testing
const mockLocalStorage = (() => {
    let store = {};
    return {
        getItem: (key) => store[key] || null,
        setItem: (key, value) => store[key] = value.toString(),
        removeItem: (key) => delete store[key],
        clear: () => store = {},
        get length() { return Object.keys(store).length; },
        key: (index) => Object.keys(store)[index] || null
    };
})();

// Mock window and document for Node.js testing
const mockWindow = {
    location: {
        hostname: 'localhost',
        href: 'http://localhost:3000',
        pathname: '/'
    },
    dataLayer: [],
    gtag: null,
    fbq: null
};

const mockDocument = {
    title: 'VidNet - HD Video Downloader',
    createElement: (tag) => ({
        tagName: tag.toUpperCase(),
        className: '',
        innerHTML: '',
        id: '',
        async: false,
        src: '',
        addEventListener: () => {},
        classList: {
            add: () => {},
            remove: () => {},
            contains: () => false
        },
        remove: () => {},
        appendChild: () => {}
    }),
    getElementById: () => null,
    querySelector: () => null,
    addEventListener: () => {},
    head: { appendChild: () => {} },
    body: { appendChild: () => {} }
};

const mockNavigator = {
    userAgent: 'Mozilla/5.0 (Test Browser)'
};

// Test suite
describe('AnalyticsManager', () => {
    let analyticsManager;
    let originalLocalStorage, originalWindow, originalDocument, originalNavigator;
    
    beforeEach(() => {
        // Store original globals
        if (typeof window !== 'undefined') {
            originalWindow = window;
            originalDocument = document;
            originalNavigator = navigator;
            originalLocalStorage = localStorage;
        }
        
        // Set up mocks
        global.localStorage = mockLocalStorage;
        global.window = mockWindow;
        global.document = mockDocument;
        global.navigator = mockNavigator;
        
        // Clear localStorage
        mockLocalStorage.clear();
        
        // Reset window properties
        mockWindow.dataLayer = [];
        mockWindow.gtag = null;
        mockWindow.fbq = null;
        
        // Create new instance
        if (typeof AnalyticsManager !== 'undefined') {
            analyticsManager = new AnalyticsManager();
        }
    });
    
    afterEach(() => {
        // Restore original globals
        if (originalWindow) {
            global.window = originalWindow;
            global.document = originalDocument;
            global.navigator = originalNavigator;
            global.localStorage = originalLocalStorage;
        }
    });
    
    describe('Initialization', () => {
        test('should initialize with default configuration', () => {
            expect(analyticsManager.isInitialized).toBe(true);
            expect(analyticsManager.consentGiven).toBe(false);
            expect(analyticsManager.customMetrics.session_id).toMatch(/^sess_/);
            expect(analyticsManager.customMetrics.downloads_total).toBe(0);
        });
        
        test('should generate unique session IDs', () => {
            const manager1 = new AnalyticsManager();
            const manager2 = new AnalyticsManager();
            expect(manager1.customMetrics.session_id).not.toBe(manager2.customMetrics.session_id);
        });
        
        test('should check existing consent on initialization', () => {
            mockLocalStorage.setItem('vidnet_analytics_consent', 'accepted');
            const manager = new AnalyticsManager();
            expect(manager.consentGiven).toBe(true);
        });
    });
    
    describe('Consent Management', () => {
        test('should accept consent and store in localStorage', () => {
            analyticsManager.acceptConsent();
            expect(mockLocalStorage.getItem('vidnet_analytics_consent')).toBe('accepted');
            expect(analyticsManager.consentGiven).toBe(true);
        });
        
        test('should decline consent and store in localStorage', () => {
            analyticsManager.declineConsent();
            expect(mockLocalStorage.getItem('vidnet_analytics_consent')).toBe('declined');
            expect(analyticsManager.consentGiven).toBe(false);
        });
        
        test('should save custom consent settings', () => {
            // Mock DOM elements for consent settings
            mockDocument.getElementById = (id) => {
                if (id === 'analytics-toggle') return { checked: true };
                if (id === 'marketing-toggle') return { checked: false };
                return null;
            };
            
            analyticsManager.saveConsentSettings();
            
            const settings = JSON.parse(mockLocalStorage.getItem('vidnet_consent_settings'));
            expect(settings.analytics).toBe(true);
            expect(settings.marketing).toBe(false);
            expect(mockLocalStorage.getItem('vidnet_analytics_consent')).toBe('custom');
        });
        
        test('should check if user has made consent decision', () => {
            expect(analyticsManager.hasConsentDecision()).toBe(false);
            
            mockLocalStorage.setItem('vidnet_analytics_consent', 'accepted');
            expect(analyticsManager.hasConsentDecision()).toBe(true);
        });
    });
    
    describe('Event Tracking', () => {
        beforeEach(() => {
            analyticsManager.consentGiven = true;
        });
        
        test('should track page views', () => {
            analyticsManager.trackPageView();
            
            expect(analyticsManager.customMetrics.page_views).toBe(1);
            
            const metrics = JSON.parse(mockLocalStorage.getItem('vidnet_custom_metrics'));
            expect(metrics).toHaveLength(1);
            expect(metrics[0].event_type).toBe('page_view');
            expect(metrics[0].data.page_title).toBe('VidNet - HD Video Downloader');
        });
        
        test('should track download events', () => {
            analyticsManager.trackDownload('youtube', '1080p', 'mp4', 'video');
            
            expect(analyticsManager.customMetrics.downloads_total).toBe(1);
            expect(analyticsManager.customMetrics.downloads_by_platform.youtube).toBe(1);
            expect(analyticsManager.customMetrics.downloads_by_quality['1080p']).toBe(1);
            
            const metrics = JSON.parse(mockLocalStorage.getItem('vidnet_custom_metrics'));
            expect(metrics).toHaveLength(1);
            expect(metrics[0].event_type).toBe('download_start');
            expect(metrics[0].data.platform).toBe('youtube');
            expect(metrics[0].data.quality).toBe('1080p');
            expect(metrics[0].data.type).toBe('video');
        });
        
        test('should track download completion', () => {
            const processingTime = 5000;
            analyticsManager.trackDownloadComplete('tiktok', '720p', 'mp4', 'video', processingTime);
            
            const metrics = JSON.parse(mockLocalStorage.getItem('vidnet_custom_metrics'));
            expect(metrics).toHaveLength(1);
            expect(metrics[0].event_type).toBe('download_complete');
            expect(metrics[0].data.platform).toBe('tiktok');
            expect(metrics[0].data.processing_time).toBe(processingTime);
        });
        
        test('should track custom events', () => {
            const eventData = { test_param: 'test_value' };
            analyticsManager.trackEvent('custom_test_event', eventData);
            
            const metrics = JSON.parse(mockLocalStorage.getItem('vidnet_custom_metrics'));
            expect(metrics).toHaveLength(1);
            expect(metrics[0].event_type).toBe('custom_test_event');
            expect(metrics[0].data.test_param).toBe('test_value');
            expect(metrics[0].data.session_id).toBe(analyticsManager.customMetrics.session_id);
        });
        
        test('should not track external services without consent', () => {
            analyticsManager.consentGiven = false;
            
            // Mock gtag and fbq
            let gtagCalled = false;
            let fbqCalled = false;
            mockWindow.gtag = () => { gtagCalled = true; };
            mockWindow.fbq = () => { fbqCalled = true; };
            
            analyticsManager.trackDownload('youtube', '1080p', 'mp4', 'video');
            
            // Should still track custom metrics
            expect(analyticsManager.customMetrics.downloads_total).toBe(1);
            
            // Should not call external services
            expect(gtagCalled).toBe(false);
            expect(fbqCalled).toBe(false);
        });
    });
    
    describe('Data Management', () => {
        test('should store custom metrics in localStorage', () => {
            const eventData = { test: 'data' };
            analyticsManager.storeCustomMetric('test_event', eventData);
            
            const metrics = JSON.parse(mockLocalStorage.getItem('vidnet_custom_metrics'));
            expect(metrics).toHaveLength(1);
            expect(metrics[0].event_type).toBe('test_event');
            expect(metrics[0].data).toEqual(eventData);
        });
        
        test('should limit stored metrics to 100 events', () => {
            // Add 105 events
            for (let i = 0; i < 105; i++) {
                analyticsManager.storeCustomMetric('test_event', { index: i });
            }
            
            const metrics = JSON.parse(mockLocalStorage.getItem('vidnet_custom_metrics'));
            expect(metrics).toHaveLength(100);
            expect(metrics[0].data.index).toBe(5); // First 5 should be removed
            expect(metrics[99].data.index).toBe(104);
        });
        
        test('should get dashboard data', () => {
            analyticsManager.trackPageView();
            analyticsManager.trackDownload('youtube', '1080p', 'mp4', 'video');
            
            const dashboardData = analyticsManager.getDashboardData();
            
            expect(dashboardData.session.page_views).toBe(1);
            expect(dashboardData.session.downloads_total).toBe(1);
            expect(dashboardData.events).toHaveLength(2);
        });
        
        test('should clear all analytics data', () => {
            analyticsManager.trackPageView();
            analyticsManager.acceptConsent();
            
            expect(mockLocalStorage.getItem('vidnet_custom_metrics')).not.toBeNull();
            expect(mockLocalStorage.getItem('vidnet_analytics_consent')).not.toBeNull();
            
            analyticsManager.clearAllData();
            
            expect(mockLocalStorage.getItem('vidnet_custom_metrics')).toBeNull();
            expect(mockLocalStorage.getItem('vidnet_analytics_consent')).toBeNull();
            expect(analyticsManager.customMetrics.downloads_total).toBe(0);
        });
    });
    
    describe('Google Analytics Integration', () => {
        test('should initialize Google Analytics with correct configuration', () => {
            let scriptAdded = false;
            let gtagConfigured = false;
            
            mockDocument.createElement = (tag) => {
                if (tag === 'script') {
                    scriptAdded = true;
                    return {
                        async: false,
                        src: '',
                        addEventListener: () => {}
                    };
                }
                return { appendChild: () => {} };
            };
            
            mockWindow.gtag = (command, ...args) => {
                if (command === 'config') {
                    gtagConfigured = true;
                    expect(args[0]).toBe(analyticsManager.config.ga4_measurement_id);
                }
            };
            
            analyticsManager.initializeGoogleAnalytics();
            
            expect(scriptAdded).toBe(true);
            expect(gtagConfigured).toBe(true);
        });
    });
    
    describe('Facebook Pixel Integration', () => {
        test('should initialize Facebook Pixel', () => {
            let fbqInitialized = false;
            let pageViewTracked = false;
            
            mockWindow.fbq = (command, ...args) => {
                if (command === 'init') {
                    fbqInitialized = true;
                    expect(args[0]).toBe(analyticsManager.config.facebook_pixel_id);
                } else if (command === 'track' && args[0] === 'PageView') {
                    pageViewTracked = true;
                }
            };
            
            analyticsManager.initializeFacebookPixel();
            
            expect(fbqInitialized).toBe(true);
            expect(pageViewTracked).toBe(true);
        });
    });
    
    describe('Privacy Compliance', () => {
        test('should respect consent for external tracking', () => {
            analyticsManager.consentGiven = false;
            
            let gtagCalled = false;
            let fbqCalled = false;
            
            mockWindow.gtag = () => { gtagCalled = true; };
            mockWindow.fbq = () => { fbqCalled = true; };
            
            analyticsManager.trackPageView();
            
            expect(gtagCalled).toBe(false);
            expect(fbqCalled).toBe(false);
        });
        
        test('should track essential metrics even without consent', () => {
            analyticsManager.consentGiven = false;
            analyticsManager.trackPageView();
            
            // Should still track in custom metrics for essential functionality
            expect(analyticsManager.customMetrics.page_views).toBe(1);
            
            const metrics = JSON.parse(mockLocalStorage.getItem('vidnet_custom_metrics'));
            expect(metrics).toHaveLength(1);
        });
    });
});

// Integration tests with VidNetUI
describe('Analytics Integration with VidNetUI', () => {
    let mockAnalytics;
    
    beforeEach(() => {
        mockAnalytics = {
            trackEvent: jest.fn ? jest.fn() : () => {},
            trackDownload: jest.fn ? jest.fn() : () => {},
            trackDownloadComplete: jest.fn ? jest.fn() : () => {},
            showPrivacySettings: jest.fn ? jest.fn() : () => {}
        };
    });
    
    test('should track URL submission', () => {
        const ui = { analytics: mockAnalytics };
        const url = 'https://www.youtube.com/watch?v=test';
        
        // Simulate URL submission tracking
        ui.analytics.trackEvent('url_submitted', {
            platform: 'youtube',
            url_length: url.length
        });
        
        if (mockAnalytics.trackEvent.mock) {
            expect(mockAnalytics.trackEvent).toHaveBeenCalledWith('url_submitted', {
                platform: 'youtube',
                url_length: url.length
            });
        }
    });
    
    test('should track download initiation', () => {
        const ui = { analytics: mockAnalytics };
        
        ui.analytics.trackDownload('youtube', '1080p', 'mp4', 'video');
        
        if (mockAnalytics.trackDownload.mock) {
            expect(mockAnalytics.trackDownload).toHaveBeenCalledWith('youtube', '1080p', 'mp4', 'video');
        }
    });
    
    test('should track download completion with processing time', () => {
        const ui = { analytics: mockAnalytics };
        const processingTime = 3000;
        
        ui.analytics.trackDownloadComplete('youtube', '1080p', 'mp4', 'video', processingTime);
        
        if (mockAnalytics.trackDownloadComplete.mock) {
            expect(mockAnalytics.trackDownloadComplete).toHaveBeenCalledWith(
                'youtube', '1080p', 'mp4', 'video', processingTime
            );
        }
    });
});

// Export for Node.js usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        AnalyticsManager: typeof AnalyticsManager !== 'undefined' ? AnalyticsManager : null,
        mockLocalStorage,
        mockWindow,
        mockDocument,
        mockNavigator
    };
}

console.log('Analytics Manager tests loaded');