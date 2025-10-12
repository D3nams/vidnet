#!/usr/bin/env node

/**
 * Node.js test runner for VidNet UI tests
 * Run with: node test_frontend.js
 */

const fs = require('fs');
const path = require('path');

// Mock browser globals for Node.js environment
global.window = {};
global.document = {
    getElementById: () => ({
        classList: { add: () => {}, remove: () => {} },
        addEventListener: () => {},
        textContent: '',
        innerHTML: '',
        appendChild: () => {},
        querySelector: () => ({ textContent: '', classList: { add: () => {}, remove: () => {} } }),
        style: {},
        disabled: false,
        value: '',
        focus: () => {}
    }),
    createElement: () => ({
        className: '',
        innerHTML: '',
        querySelector: () => ({ addEventListener: () => {} }),
        appendChild: () => {}
    }),
    addEventListener: () => {}
};

// Mock fetch for API calls
global.fetch = async (url, options) => {
    // Mock successful responses for testing
    if (url.includes('/metadata')) {
        return {
            ok: true,
            json: async () => ({
                title: 'Test Video',
                thumbnail: 'https://example.com/thumb.jpg',
                duration: 180,
                platform: 'youtube',
                available_qualities: [
                    { quality: '720p', format: 'mp4', filesize: 50000000 },
                    { quality: '1080p', format: 'mp4', filesize: 100000000 }
                ],
                audio_available: true,
                original_url: 'https://youtube.com/watch?v=test'
            })
        };
    }
    
    if (url.includes('/download') || url.includes('/extract-audio')) {
        return {
            ok: true,
            json: async () => ({
                task_id: 'test-task-123',
                status: 'pending'
            })
        };
    }
    
    if (url.includes('/status/')) {
        return {
            ok: true,
            json: async () => ({
                status: 'completed',
                download_url: 'https://example.com/download/test.mp4'
            })
        };
    }
    
    throw new Error('Unknown endpoint');
};

// Load and execute the VidNet UI code
try {
    const vidnetUICode = fs.readFileSync(path.join(__dirname, 'static/js/vidnet-ui.js'), 'utf8');
    // Remove the DOM ready event listener for Node.js
    const cleanedUICode = vidnetUICode.replace(/document\.addEventListener\('DOMContentLoaded'[^}]+\}\);?/g, '');
    eval(cleanedUICode);
    
    // Make VidNetUI globally available
    global.VidNetUI = VidNetUI;
    
    console.log('✅ VidNet UI code loaded successfully');
} catch (error) {
    console.error('❌ Failed to load VidNet UI code:', error.message);
    process.exit(1);
}

// Load and execute the test code
try {
    const testCode = fs.readFileSync(path.join(__dirname, 'static/js/vidnet-ui.test.js'), 'utf8');
    eval(testCode);
    console.log('✅ Test code loaded successfully');
} catch (error) {
    console.error('❌ Failed to load test code:', error.message);
    process.exit(1);
}

// Run the tests
async function runTests() {
    console.log('\n🚀 Running VidNet UI Tests in Node.js environment...\n');
    
    try {
        const results = await module.exports.runAll();
        
        console.log('\n' + '='.repeat(50));
        if (results.failed === 0) {
            console.log('🎉 All tests passed!');
            process.exit(0);
        } else {
            console.log(`💥 ${results.failed} test(s) failed!`);
            process.exit(1);
        }
    } catch (error) {
        console.error('❌ Test execution failed:', error.message);
        process.exit(1);
    }
}

// Run tests if this file is executed directly
if (require.main === module) {
    runTests();
}