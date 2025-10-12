/**
 * Simple Analytics Test Runner for Node.js
 * Tests the analytics manager functionality without browser dependencies
 */

// Mock browser environment
global.window = {
    location: {
        hostname: 'localhost',
        href: 'http://localhost:3000',
        pathname: '/'
    },
    dataLayer: [],
    gtag: null,
    fbq: null
};

global.document = {
    title: 'VidNet - HD Video Downloader',
    createElement: () => ({
        tagName: 'SCRIPT',
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

global.navigator = {
    userAgent: 'Mozilla/5.0 (Test Browser)'
};

// Mock localStorage
global.localStorage = {
    store: {},
    getItem: function(key) { return this.store[key] || null; },
    setItem: function(key, value) { this.store[key] = value.toString(); },
    removeItem: function(key) { delete this.store[key]; },
    clear: function() { this.store = {}; }
};

// Mock fetch for backend communication
global.fetch = async (url, options) => {
    console.log(`Mock fetch: ${options?.method || 'GET'} ${url}`);
    return {
        ok: true,
        status: 200,
        json: async () => ({ success: true, message: 'Mock response' })
    };
};

// Load the analytics manager
const AnalyticsManager = require('./static/js/analytics-manager.js');

// Test runner
class SimpleTestRunner {
    constructor() {
        this.tests = [];
        this.results = [];
    }
    
    test(name, testFn) {
        this.tests.push({ name, testFn });
    }
    
    expect(actual) {
        return {
            toBe: (expected) => {
                if (actual === expected) {
                    return { passed: true };
                } else {
                    throw new Error(`Expected ${actual} to be ${expected}`);
                }
            },
            toContain: (expected) => {
                if (actual && actual.includes && actual.includes(expected)) {
                    return { passed: true };
                } else {
                    throw new Error(`Expected ${actual} to contain ${expected}`);
                }
            },
            toBeGreaterThan: (expected) => {
                if (actual > expected) {
                    return { passed: true };
                } else {
                    throw new Error(`Expected ${actual} to be greater than ${expected}`);
                }
            }
        };
    }
    
    async run() {
        console.log('🎬 VidNet Analytics Manager - Simple Test Suite\n');
        
        let passed = 0;
        let failed = 0;
        
        for (const test of this.tests) {
            try {
                await test.testFn();
                console.log(`✓ ${test.name}`);
                passed++;
            } catch (error) {
                console.log(`✗ ${test.name}: ${error.message}`);
                failed++;
            }
        }
        
        console.log(`\nResults: ${passed} passed, ${failed} failed`);
        
        if (failed === 0) {
            console.log('🎉 All tests passed!');
        } else {
            console.log('❌ Some tests failed');
            process.exit(1);
        }
    }
}

// Initialize test runner
const testRunner = new SimpleTestRunner();

// Test analytics manager initialization
testRunner.test('Analytics Manager Initialization', () => {
    const analytics = new AnalyticsManager();
    testRunner.expect(analytics.isInitialized).toBe(true);
    testRunner.expect(analytics.customMetrics.session_id).toContain('sess_');
});

// Test session ID generation
testRunner.test('Session ID Generation', () => {
    const analytics = new AnalyticsManager();
    const sessionId = analytics.generateSessionId();
    testRunner.expect(sessionId).toContain('sess_');
    testRunner.expect(sessionId.length).toBeGreaterThan(10);
});

// Test consent management
testRunner.test('Consent Management', () => {
    const analytics = new AnalyticsManager();
    
    // Test accept consent
    analytics.acceptConsent();
    testRunner.expect(localStorage.getItem('vidnet_analytics_consent')).toBe('accepted');
    testRunner.expect(analytics.consentGiven).toBe(true);
    
    // Test decline consent
    analytics.declineConsent();
    testRunner.expect(localStorage.getItem('vidnet_analytics_consent')).toBe('declined');
    testRunner.expect(analytics.consentGiven).toBe(false);
});

// Test event tracking
testRunner.test('Event Tracking', () => {
    const analytics = new AnalyticsManager();
    analytics.consentGiven = true;
    
    const initialPageViews = analytics.customMetrics.page_views;
    analytics.trackPageView();
    testRunner.expect(analytics.customMetrics.page_views).toBe(initialPageViews + 1);
    
    const metrics = JSON.parse(localStorage.getItem('vidnet_custom_metrics') || '[]');
    const pageViewEvents = metrics.filter(m => m.event_type === 'page_view');
    testRunner.expect(pageViewEvents.length).toBeGreaterThan(0);
});

// Test download tracking
testRunner.test('Download Tracking', () => {
    const analytics = new AnalyticsManager();
    analytics.consentGiven = true;
    
    const initialDownloads = analytics.customMetrics.downloads_total;
    analytics.trackDownload('youtube', '1080p', 'mp4', 'video');
    
    testRunner.expect(analytics.customMetrics.downloads_total).toBe(initialDownloads + 1);
    testRunner.expect(analytics.customMetrics.downloads_by_platform.youtube).toBeGreaterThan(0);
    testRunner.expect(analytics.customMetrics.downloads_by_quality['1080p']).toBeGreaterThan(0);
});

// Test custom event tracking
testRunner.test('Custom Event Tracking', () => {
    const analytics = new AnalyticsManager();
    analytics.consentGiven = true;
    
    const eventData = { test_param: 'test_value', number_param: 42 };
    analytics.trackEvent('test_custom_event', eventData);
    
    const metrics = JSON.parse(localStorage.getItem('vidnet_custom_metrics') || '[]');
    const customEvents = metrics.filter(m => m.event_type === 'test_custom_event');
    testRunner.expect(customEvents.length).toBeGreaterThan(0);
    
    const lastEvent = customEvents[customEvents.length - 1];
    testRunner.expect(lastEvent.data.test_param).toBe('test_value');
    testRunner.expect(lastEvent.data.number_param).toBe(42);
});

// Test data clearing
testRunner.test('Data Clearing', () => {
    const analytics = new AnalyticsManager();
    
    // Add some data
    analytics.trackPageView();
    analytics.acceptConsent();
    
    testRunner.expect(localStorage.getItem('vidnet_custom_metrics')).toContain('page_view');
    testRunner.expect(localStorage.getItem('vidnet_analytics_consent')).toBe('accepted');
    
    // Clear data
    analytics.clearAllData();
    
    testRunner.expect(localStorage.getItem('vidnet_custom_metrics')).toBe(null);
    testRunner.expect(localStorage.getItem('vidnet_analytics_consent')).toBe(null);
    testRunner.expect(analytics.customMetrics.downloads_total).toBe(0);
});

// Test dashboard data retrieval
testRunner.test('Dashboard Data Retrieval', () => {
    const analytics = new AnalyticsManager();
    analytics.trackPageView();
    analytics.trackDownload('youtube', '1080p', 'mp4', 'video');
    
    const dashboardData = analytics.getDashboardData();
    
    testRunner.expect(dashboardData.session.page_views).toBeGreaterThan(0);
    testRunner.expect(dashboardData.session.downloads_total).toBeGreaterThan(0);
    testRunner.expect(Array.isArray(dashboardData.events)).toBe(true);
});

// Run all tests
testRunner.run().catch(console.error);