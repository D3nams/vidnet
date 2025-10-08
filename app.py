from flask import Flask, render_template, request, send_from_directory
from extractor import extract_video_data_from_url

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ads.txt')
def ads_txt():
    return send_from_directory(app.root_path, 'ads.txt')

@app.route('/download', methods=['POST'])
def download():
    url = request.form['url']
    video_data = extract_video_data_from_url(url)
    return render_template('download.html', **video_data)

