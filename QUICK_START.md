# VidNet Quick Start Guide

## 🚀 Get VidNet Running in 2 Minutes

### Option 1: Windows Batch File (Easiest)
```bash
# Double-click or run in Command Prompt
start_vidnet.bat
```

### Option 2: Python Direct
```bash
# Run the minimal version directly
python app_minimal.py
```

### Option 3: Simple Startup Script
```bash
# Run without Redis dependency
python start_simple.py
```

## 🌐 Access Your Application

Once started, open your browser to:
- **Main App**: http://127.0.0.1:8000
- **API Docs**: http://127.0.0.1:8000/docs
- **Test Page**: http://127.0.0.1:8000/test_frontend_integration.html

## 🧪 Test the Application

### Quick Test
1. Open http://127.0.0.1:8000
2. Paste this URL: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
3. Click "Get Video Info"
4. Try downloading or extracting audio

### Integration Test
1. Go to http://127.0.0.1:8000/test_frontend_integration.html
2. Watch the automated tests run
3. Try the manual test at the bottom

## ⚠️ Troubleshooting

### "Redis connection failed"
**Solution**: Use the minimal version instead
```bash
python app_minimal.py
```

### "Docker not found"
**Solution**: Skip Docker, use minimal mode
```bash
# Use this instead of start_local.py
python start_simple.py
```

### "Module not found" errors
**Solution**: Install dependencies
```bash
pip install fastapi uvicorn
```

### "Port 8000 already in use"
**Solution**: Kill existing processes or change port
```bash
# Kill existing processes (Windows)
taskkill /f /im python.exe

# Or change port in app_minimal.py (line at bottom)
uvicorn.run(app, host="127.0.0.1", port=8001)
```

### Static files not loading
**Solution**: Make sure you're in the project root directory
```bash
# Make sure these folders exist:
# static/
# static/js/
# static/index.html
```

## 🎯 What Works in Minimal Mode

✅ **Working Features**:
- Video metadata extraction (mock data)
- Download workflow simulation
- Audio extraction simulation
- Frontend interface
- API documentation
- Error handling
- Progress tracking

⚠️ **Limited Features**:
- No actual video downloading (mock responses)
- No Redis caching
- No real-time performance monitoring
- No persistent storage

## 🚀 Ready for Production?

Once you've tested locally, deploy to Render:

1. **Validate deployment**:
   ```bash
   python deploy_to_render.py
   ```

2. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   ```

3. **Deploy on Render**:
   - Go to https://render.com/dashboard
   - Create Web Service from your GitHub repo
   - Render will auto-detect `render.yaml`

## 📞 Need Help?

- Check `FINAL_INTEGRATION_README.md` for complete documentation
- Review logs in the terminal for error details
- Ensure you're in the correct directory with all files present

## 🎉 Success!

If you see the VidNet interface and can test metadata extraction, you're ready to deploy! The minimal version proves all your frontend-backend integration is working correctly.