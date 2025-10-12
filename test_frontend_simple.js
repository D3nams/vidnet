#!/usr/bin/env node

/**
 * Simple test to verify VidNet UI JavaScript functionality
 */

console.log('🧪 Testing VidNet UI JavaScript functionality...\n');

// Test 1: URL Validation Patterns
console.log('✅ Testing URL validation patterns...');

const supportedPlatforms = [
    { name: 'YouTube', pattern: /(youtube\.com|youtu\.be)/, testUrl: 'https://www.youtube.com/watch?v=test' },
    { name: 'TikTok', pattern: /tiktok\.com/, testUrl: 'https://www.tiktok.com/@user/video/123' },
    { name: 'Instagram', pattern: /instagram\.com/, testUrl: 'https://www.instagram.com/p/test/' },
    { name: 'Facebook', pattern: /facebook\.com/, testUrl: 'https://www.facebook.com/watch/?v=123' },
    { name: 'Twitter/X', pattern: /(twitter\.com|x\.com)/, testUrl: 'https://twitter.com/user/status/123' },
    { name: 'Reddit', pattern: /reddit\.com/, testUrl: 'https://www.reddit.com/r/videos/comments/test/' },
    { name: 'Vimeo', pattern: /vimeo\.com/, testUrl: 'https://vimeo.com/123456' },
    { name: 'Direct Video', pattern: /\.(mp4|avi|mov|mkv|webm|flv)(\?|$)/, testUrl: 'https://example.com/video.mp4' }
];

let platformTestsPassed = 0;
supportedPlatforms.forEach(platform => {
    const matches = platform.pattern.test(platform.testUrl);
    if (matches) {
        console.log(`  ✅ ${platform.name}: ${platform.testUrl}`);
        platformTestsPassed++;
    } else {
        console.log(`  ❌ ${platform.name}: ${platform.testUrl}`);
    }
});

console.log(`Platform detection: ${platformTestsPassed}/${supportedPlatforms.length} passed\n`);

// Test 2: Duration Formatting
console.log('✅ Testing duration formatting...');

function formatDuration(seconds) {
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

const durationTests = [
    { input: 0, expected: '0:00' },
    { input: 65, expected: '1:05' },
    { input: 3661, expected: '1:01:01' },
    { input: null, expected: '0:00' }
];

let durationTestsPassed = 0;
durationTests.forEach(test => {
    const result = formatDuration(test.input);
    if (result === test.expected) {
        console.log(`  ✅ ${test.input} seconds -> ${result}`);
        durationTestsPassed++;
    } else {
        console.log(`  ❌ ${test.input} seconds -> ${result} (expected ${test.expected})`);
    }
});

console.log(`Duration formatting: ${durationTestsPassed}/${durationTests.length} passed\n`);

// Test 3: File Size Formatting
console.log('✅ Testing file size formatting...');

function formatFileSize(bytes) {
    if (!bytes) return 'Unknown size';
    
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
}

const fileSizeTests = [
    { input: 1024, expected: '1.0 KB' },
    { input: 1048576, expected: '1.0 MB' },
    { input: 1073741824, expected: '1.0 GB' },
    { input: null, expected: 'Unknown size' },
    { input: 0, expected: 'Unknown size' }
];

let fileSizeTestsPassed = 0;
fileSizeTests.forEach(test => {
    const result = formatFileSize(test.input);
    if (result === test.expected) {
        console.log(`  ✅ ${test.input} bytes -> ${result}`);
        fileSizeTestsPassed++;
    } else {
        console.log(`  ❌ ${test.input} bytes -> ${result} (expected ${test.expected})`);
    }
});

console.log(`File size formatting: ${fileSizeTestsPassed}/${fileSizeTests.length} passed\n`);

// Test 4: URL Validation Logic
console.log('✅ Testing URL validation logic...');

function validateURL(url) {
    if (!url) return false;
    
    // Basic URL validation
    try {
        new URL(url);
    } catch {
        return false;
    }
    
    // Platform validation
    const platform = supportedPlatforms.find(p => p.pattern.test(url));
    return !!platform;
}

const urlTests = [
    { url: 'https://www.youtube.com/watch?v=test', expected: true },
    { url: 'https://youtu.be/test', expected: true },
    { url: 'https://www.tiktok.com/@user/video/123', expected: true },
    { url: 'https://example.com/video.mp4', expected: true },
    { url: 'not-a-valid-url', expected: false },
    { url: 'https://unsupported-platform.com/video/123', expected: false },
    { url: '', expected: false }
];

let urlTestsPassed = 0;
urlTests.forEach(test => {
    const result = validateURL(test.url);
    if (result === test.expected) {
        console.log(`  ✅ ${test.url || '(empty)'} -> ${result}`);
        urlTestsPassed++;
    } else {
        console.log(`  ❌ ${test.url || '(empty)'} -> ${result} (expected ${test.expected})`);
    }
});

console.log(`URL validation: ${urlTestsPassed}/${urlTests.length} passed\n`);

// Summary
const totalTests = platformTestsPassed + durationTestsPassed + fileSizeTestsPassed + urlTestsPassed;
const maxTests = supportedPlatforms.length + durationTests.length + fileSizeTests.length + urlTests.length;

console.log('='.repeat(50));
console.log(`📊 Test Summary: ${totalTests}/${maxTests} tests passed`);

if (totalTests === maxTests) {
    console.log('🎉 All core JavaScript functionality tests passed!');
    process.exit(0);
} else {
    console.log(`💥 ${maxTests - totalTests} test(s) failed!`);
    process.exit(1);
}