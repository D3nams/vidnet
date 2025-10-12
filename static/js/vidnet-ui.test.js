/**
 * VidNet UI Unit Tests
 * Simple test framework for frontend functionality
 */

class TestFramework {
    constructor() {
        this.tests = [];
        this.passed = 0;
        this.failed = 0;
    }
    
    test(name, testFn) {
        this.tests.push({ name, testFn });
    }
    
    async runAll() {
        console.log('🧪 Running VidNet UI Tests...\n');
        
        for (const test of this.tests) {
            try {
                await test.testFn();
                this.passed++;
                console.log(`✅ ${test.name}`);
            } catch (error) {
                this.failed++;
                console.error(`❌ ${test.name}: ${error.message}`);
            }
        }
        
        console.log(`\n📊 Test Results: ${this.passed} passed, ${this.failed} failed`);
        return { passed: this.passed, failed: this.failed };
    }
    
    assert(condition, message) {
        if (!condition) {
            throw new Error(message || 'Assertion failed');
        }
    }
    
    assertEqual(actual, expected, message) {
        if (actual !== expected) {
            throw new Error(message || `Expected ${expected}, got ${actual}`);
        }
    }
    
    assertContains(container, item, message) {
        if (!container.includes(item)) {
            throw new Error(message || `Expected container to include ${item}`);
        }
    }
}

// Test suite
const testFramework = new TestFramework();

// Mock DOM elements for testing
function createMockDOM() {
    // Create a minimal DOM structure for testing
    const mockElements = {
        'url-form': { addEventListener: () => {} },
        'video-url': { 
            value: '', 
            addEventListener: () => {},
            focus: () => {},
            disabled: false
        },
        'url-feedback': { classList: { add: () => {}, remove: () => {} } },
        'url-error': { classList: { add: () => {}, remove: () => {} } },
        'url-success': { classList: { add: () => {}, remove: () => {} } },
        'url-error-message': { textContent: '' },
        'url-success-message': { textContent: '' },
        'url-status-icon': { classList: { add: () => {}, remove: () => {} } },
        'fetch-btn': { disabled: false },
        'fetch-btn-text': { textContent: 'Get Video Info' },
        'fetch-btn-loading': { classList: { add: () => {}, remove: () => {} } },
        'retry-button': { addEventListener: () => {} },
        'download-another': { addEventListener: () => {} },
        'metadata-section': { classList: { add: () => {}, remove: () => {} } },
        'progress-section': { classList: { add: () => {}, remove: () => {} } },
        'download-complete-section': { classList: { add: () => {}, remove: () => {} } },
        'error-section': { classList: { add: () => {}, remove: () => {} } },
        'video-thumbnail': { src: '', alt: '' },
        'video-title': { textContent: '' },
        'video-duration': { querySelector: () => ({ textContent: '' }) },
        'video-platform': { querySelector: () => ({ textContent: '' }) },
        'video-qualities': { innerHTML: '', appendChild: () => {} },
        'audio-qualities': { innerHTML: '', appendChild: () => {} },
        'audio-section': { style: { display: '' } },
        'progress-bar': { style: { width: '' } },
        'progress-text': { textContent: '' },
        'progress-percentage': { textContent: '' },
        'step-validate': { classList: { add: () => {}, remove: () => {} }, querySelector: () => ({ classList: { add: () => {}, remove: () => {} } }) },
        'step-extract': { classList: { add: () => {}, remove: () => {} }, querySelector: () => ({ classList: { add: () => {}, remove: () => {} } }) },
        'step-process': { classList: { add: () => {}, remove: () => {} }, querySelector: () => ({ classList: { add: () => {}, remove: () => {} } }) },
        'step-complete': { classList: { add: () => {}, remove: () => {} }, querySelector: () => ({ classList: { add: () => {}, remove: () => {} } }) },
        'download-link': { href: '' },
        'cleanup-timer': { textContent: '' },
        'error-message': { textContent: '' },
        'error-suggestions': { innerHTML: '', appendChild: () => {} }
    };
    
    // Mock document.getElementById
    global.document = {
        getElementById: (id) => mockElements[id] || { 
            classList: { add: () => {}, remove: () => {} },
            addEventListener: () => {},
            textContent: '',
            innerHTML: '',
            appendChild: () => {},
            querySelector: () => ({ textContent: '', classList: { add: () => {}, remove: () => {} } })
        },
        createElement: (tag) => ({
            className: '',
            innerHTML: '',
            querySelector: () => ({ addEventListener: () => {} }),
            appendChild: () => {}
        }),
        addEventListener: () => {}
    };
    
    return mockElements;
}

// Test: VidNetUI Initialization
testFramework.test('VidNetUI should initialize correctly', () => {
    const mockElements = createMockDOM();
    
    // Mock console.log to capture initialization message
    let logMessage = '';
    const originalLog = console.log;
    console.log = (msg) => { logMessage = msg; };
    
    const ui = new VidNetUI();
    
    // Restore console.log
    console.log = originalLog;
    
    testFramework.assert(ui.apiBase === '/api/v1', 'API base should be set correctly');
    testFramework.assert(ui.currentRequest === null, 'Current request should be null initially');
    testFramework.assert(ui.currentTaskId === null, 'Current task ID should be null initially');
    testFramework.assertEqual(logMessage, 'VidNet UI initialized', 'Should log initialization message');
});

// Test: URL Validation - Valid URLs
testFramework.test('URL validation should accept valid YouTube URLs', () => {
    const mockElements = createMockDOM();
    const ui = new VidNetUI();
    
    // Set a valid YouTube URL
    mockElements['video-url'].value = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';
    
    const isValid = ui.validateURL();
    testFramework.assert(isValid === true, 'Should validate YouTube URL as valid');
});

testFramework.test('URL validation should accept valid TikTok URLs', () => {
    const mockElements = createMockDOM();
    const ui = new VidNetUI();
    
    mockElements['video-url'].value = 'https://www.tiktok.com/@user/video/1234567890';
    
    const isValid = ui.validateURL();
    testFramework.assert(isValid === true, 'Should validate TikTok URL as valid');
});

testFramework.test('URL validation should accept direct video links', () => {
    const mockElements = createMockDOM();
    const ui = new VidNetUI();
    
    mockElements['video-url'].value = 'https://example.com/video.mp4';
    
    const isValid = ui.validateURL();
    testFramework.assert(isValid === true, 'Should validate direct video link as valid');
});

// Test: URL Validation - Invalid URLs
testFramework.test('URL validation should reject invalid URLs', () => {
    const mockElements = createMockDOM();
    const ui = new VidNetUI();
    
    mockElements['video-url'].value = 'not-a-valid-url';
    
    const isValid = ui.validateURL();
    testFramework.assert(isValid === false, 'Should reject invalid URL format');
});

testFramework.test('URL validation should reject unsupported platforms', () => {
    const mockElements = createMockDOM();
    const ui = new VidNetUI();
    
    mockElements['video-url'].value = 'https://unsupported-platform.com/video/123';
    
    const isValid = ui.validateURL();
    testFramework.assert(isValid === false, 'Should reject unsupported platform');
});

testFramework.test('URL validation should handle empty input', () => {
    const mockElements = createMockDOM();
    const ui = new VidNetUI();
    
    mockElements['video-url'].value = '';
    
    const isValid = ui.validateURL();
    testFramework.assert(isValid === false, 'Should handle empty input gracefully');
});

// Test: Duration Formatting
testFramework.test('Duration formatting should work correctly', () => {
    const mockElements = createMockDOM();
    const ui = new VidNetUI();
    
    testFramework.assertEqual(ui.formatDuration(0), '0:00', 'Should format zero duration');
    testFramework.assertEqual(ui.formatDuration(65), '1:05', 'Should format minutes and seconds');
    testFramework.assertEqual(ui.formatDuration(3661), '1:01:01', 'Should format hours, minutes, and seconds');
    testFramework.assertEqual(ui.formatDuration(null), '0:00', 'Should handle null input');
});

// Test: File Size Formatting
testFramework.test('File size formatting should work correctly', () => {
    const mockElements = createMockDOM();
    const ui = new VidNetUI();
    
    testFramework.assertEqual(ui.formatFileSize(1024), '1.0 KB', 'Should format KB correctly');
    testFramework.assertEqual(ui.formatFileSize(1048576), '1.0 MB', 'Should format MB correctly');
    testFramework.assertEqual(ui.formatFileSize(1073741824), '1.0 GB', 'Should format GB correctly');
    testFramework.assertEqual(ui.formatFileSize(null), 'Unknown size', 'Should handle null input');
    testFramework.assertEqual(ui.formatFileSize(0), 'Unknown size', 'Should handle zero input');
});

// Test: Progress Updates
testFramework.test('Progress updates should work correctly', () => {
    const mockElements = createMockDOM();
    const ui = new VidNetUI();
    
    // Mock progress elements
    let progressBarWidth = '';
    let progressText = '';
    let progressPercentage = '';
    
    mockElements['progress-bar'].style = { 
        set width(value) { progressBarWidth = value; },
        get width() { return progressBarWidth; }
    };
    mockElements['progress-text'] = { 
        set textContent(value) { progressText = value; },
        get textContent() { return progressText; }
    };
    mockElements['progress-percentage'] = { 
        set textContent(value) { progressPercentage = value; },
        get textContent() { return progressPercentage; }
    };
    
    ui.updateProgress(75, 'Processing...');
    
    testFramework.assertEqual(progressBarWidth, '75%', 'Should update progress bar width');
    testFramework.assertEqual(progressText, 'Processing...', 'Should update progress text');
    testFramework.assertEqual(progressPercentage, '75%', 'Should update progress percentage');
});

// Test: Error Handling
testFramework.test('Error display should work correctly', () => {
    const mockElements = createMockDOM();
    const ui = new VidNetUI();
    
    let errorMessage = '';
    mockElements['error-message'] = {
        set textContent(value) { errorMessage = value; },
        get textContent() { return errorMessage; }
    };
    
    const suggestions = ['Try again', 'Check connection'];
    ui.showError('Test error message', suggestions);
    
    testFramework.assertEqual(errorMessage, 'Test error message', 'Should set error message correctly');
});

// Test: Loading State Management
testFramework.test('Loading state should be managed correctly', () => {
    const mockElements = createMockDOM();
    const ui = new VidNetUI();
    
    let fetchBtnDisabled = false;
    let fetchBtnText = '';
    let urlInputDisabled = false;
    
    mockElements['fetch-btn'] = {
        set disabled(value) { fetchBtnDisabled = value; },
        get disabled() { return fetchBtnDisabled; }
    };
    mockElements['fetch-btn-text'] = {
        set textContent(value) { fetchBtnText = value; },
        get textContent() { return fetchBtnText; }
    };
    mockElements['video-url'] = {
        set disabled(value) { urlInputDisabled = value; },
        get disabled() { return urlInputDisabled; },
        value: '',
        addEventListener: () => {},
        focus: () => {}
    };
    
    // Test loading state
    ui.setLoadingState(true);
    testFramework.assert(fetchBtnDisabled === true, 'Should disable fetch button when loading');
    testFramework.assertEqual(fetchBtnText, 'Processing...', 'Should update button text when loading');
    testFramework.assert(urlInputDisabled === true, 'Should disable URL input when loading');
    
    // Test normal state
    ui.setLoadingState(false);
    testFramework.assert(fetchBtnDisabled === false, 'Should enable fetch button when not loading');
    testFramework.assertEqual(fetchBtnText, 'Get Video Info', 'Should restore button text when not loading');
    testFramework.assert(urlInputDisabled === false, 'Should enable URL input when not loading');
});

// Test: Reset UI Functionality
testFramework.test('UI reset should work correctly', () => {
    const mockElements = createMockDOM();
    const ui = new VidNetUI();
    
    let urlValue = '';
    mockElements['video-url'] = {
        set value(val) { urlValue = val; },
        get value() { return urlValue; },
        addEventListener: () => {},
        focus: () => {},
        disabled: false
    };
    
    // Set some state
    ui.currentRequest = { url: 'test', type: 'video' };
    ui.currentTaskId = 'task123';
    urlValue = 'https://youtube.com/watch?v=test';
    
    // Reset UI
    ui.resetUI();
    
    testFramework.assertEqual(urlValue, '', 'Should clear URL input');
    testFramework.assert(ui.currentRequest === null, 'Should reset current request');
    testFramework.assert(ui.currentTaskId === null, 'Should reset current task ID');
});

// Test: Platform Detection in URL Validation
testFramework.test('Platform detection should work for all supported platforms', () => {
    const mockElements = createMockDOM();
    const ui = new VidNetUI();
    
    const testCases = [
        { url: 'https://www.youtube.com/watch?v=test', platform: 'YouTube' },
        { url: 'https://youtu.be/test', platform: 'YouTube' },
        { url: 'https://www.tiktok.com/@user/video/123', platform: 'TikTok' },
        { url: 'https://www.instagram.com/p/test/', platform: 'Instagram' },
        { url: 'https://www.facebook.com/watch/?v=123', platform: 'Facebook' },
        { url: 'https://twitter.com/user/status/123', platform: 'Twitter/X' },
        { url: 'https://x.com/user/status/123', platform: 'Twitter/X' },
        { url: 'https://www.reddit.com/r/videos/comments/test/', platform: 'Reddit' },
        { url: 'https://vimeo.com/123456', platform: 'Vimeo' },
        { url: 'https://example.com/video.mp4', platform: 'Direct Video' }
    ];
    
    testCases.forEach(testCase => {
        mockElements['video-url'].value = testCase.url;
        const isValid = ui.validateURL();
        testFramework.assert(isValid === true, `Should detect ${testCase.platform} platform for ${testCase.url}`);
    });
});

// Export test framework for browser usage
if (typeof window !== 'undefined') {
    window.VidNetUITests = testFramework;
}

// Export for Node.js usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = testFramework;
}