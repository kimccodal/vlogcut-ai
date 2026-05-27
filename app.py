from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import openai
from google import genai
import os
import json
import tempfile
import subprocess
import requests
from bs4 import BeautifulSoup
import time

app = Flask(__name__)
CORS(app)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DB_FILE = "youtubers.json"
BGM_FOLDER = "bgm"
UPLOAD_FOLDER = "uploads"

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

if not os.path.exists(BGM_FOLDER):
    os.makedirs(BGM_FOLDER)
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

current_video_path = ""

def search_web(query):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num=5"
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        texts = []
        for div in soup.find_all(['div', 'span'], class_=['BNeawe', 'VwiC3b', 'yXK7lf']):
            t = div.get_text()
            if len(t) > 30:
                texts.append(t)
        return ' '.join(texts[:5])
    except:
        return ""

def analyze_youtuber_with_gemini(name, url):
    handle = url.split('@')[-1].rstrip('/')
    
    web_info = search_web(f"{name} {handle} 유튜브 편집 스타일 브이로그 특징 자막 효과")
    web_info2 = search_web(f"{handle} youtube vlog editing style BGM music effects")
    naver_info = search_web(f"site:blog.naver.com {name} 유튜브 편집")
    
    combined_info = f"{web_info} {web_info2} {naver_info}"
    
    prompt = f"""
유튜버 {name} (@{handle}) 의 편집 스타일을 분석해주세요.

아래는 인터넷에서 수집한 정보입니다:
{combined_info[:3000]}

위 정보와 당신이 알고 있는 정보를 종합해서 아래 항목을 분석해주세요:

1. 전체 편집 스타일 (색감, 분위기, 템포)
2. 자막 스타일 (폰트, 크기 변화, 위치, 효과)
3. 개그/유머 패턴 (어떤 상황에서 어떻게 웃음을 만드는지)
4. 영상 흐름 패턴 (컷 구성, 장면 전환, 호흡)
5. BGM 특징 (주로 쓰는 음악 장르, 무드, 템포)
6. 효과음 사용 패턴 (어떤 장면에서 어떤 효과음)
7. Artlist 검색 키워드 추천 (BGM용 3개, SFX용 3개)

반드시 JSON으로만 답하세요:
{{
  "style_summary": "2-3문장 요약",
  "color_tone": "색감/분위기",
  "subtitle_style": "자막 스타일",
  "humor_pattern": "개그 패턴",
  "flow_pattern": "영상 흐름",
  "bgm_style": "BGM 특징",
  "sfx_pattern": "효과음 패턴",
  "artlist_bgm_keywords": ["키워드1", "키워드2", "키워드3"],
  "artlist_sfx_keywords": ["키워드1", "키워드2", "키워드3"]
}}
"""
    
    response = gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    
    return json.loads(text.strip())

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"youtubers": [
        {"id": 1, "name": "모하비", "url": "https://www.youtube.com/@Mojave", "ratio": 40, "style": "", "analysis": {}},
        {"id": 2, "name": "예디", "url": "https://www.youtube.com/@yedy101", "ratio": 30, "style": "", "analysis": {}},
        {"id": 3, "name": "걍밍경", "url": "https://www.youtube.com/@iammingki", "ratio": 20, "style": "", "analysis": {}},
        {"id": 4, "name": "조효진", "url": "https://www.youtube.com/@hyojin94517", "ratio": 10, "style": "", "analysis": {}}
    ]}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_combined_style():
    db = load_db()
    styles = []
    bgm_keywords = set()
    sfx_keywords = set()
    for y in db['youtubers']:
        if y['ratio'] > 0:
            analysis = y.get('analysis', {})
            style_text = y.get('style', '') or analysis.get('style_summary', '')
            styles.append(f"- {y['name']} ({y['ratio']}% 비중): {style_text}")
            for kw in analysis.get('artlist_bgm_keywords', []):
                bgm_keywords.add(kw)
            for kw in analysis.get('artlist_sfx_keywords', []):
                sfx_keywords.add(kw)
    return '\n'.join(styles), list(bgm_keywords), list(sfx_keywords)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/youtubers', methods=['GET'])
def get_youtubers():
    return jsonify(load_db())

@app.route('/youtubers/analyze-all', methods=['POST'])
def analyze_all():
    db = load_db()
    results = []
    for y in db['youtubers']:
        try:
            analysis = analyze_youtuber_with_gemini(y['name'], y['url'])
            y['analysis'] = analysis
            y['style'] = analysis.get('style_summary', '')
            results.append({'id': y['id'], 'name': y['name'], 'success': True})
            time.sleep(1)
        except Exception as e:
            results.append({'id': y['id'], 'name': y['name'], 'success': False, 'error': str(e)})
    save_db(db)
    return jsonify({'success': True, 'results': results, 'youtubers': db['youtubers']})

@app.route('/youtubers/add', methods=['POST'])
def add_youtuber():
    data = request.json
    url = data.get('url', '')
    name = data.get('name', url.split('@')[-1].rstrip('/'))
    try:
        analysis = analyze_youtuber_with_gemini(name, url)
        db = load_db()
        new_id = max([y['id'] for y in db['youtubers']], default=0) + 1
        new_youtuber = {
            "id": new_id,
            "name": name,
            "url": url,
            "ratio": data.get('ratio', 0),
            "style": analysis.get('style_summary', ''),
            "analysis": analysis
        }
        db['youtubers'].append(new_youtuber)
        save_db(db)
        return jsonify({"success": True, "youtuber": new_youtuber})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/youtubers/update-ratio', methods=['POST'])
def update_ratio():
    data = request.json
    db = load_db()
    for y in db['youtubers']:
        if y['id'] == data['id']:
            y['ratio'] = data['ratio']
    save_db(db)
    return jsonify({"success": True})

@app.route('/youtubers/delete', methods=['POST'])
def delete_youtuber():
    data = request.json
    db = load_db()
    db['youtubers'] = [y for y in db['youtubers'] if y['id'] != data['id']]
    save_db(db)
    return jsonify({"success": True})

@app.route("/transcribe", methods=["POST"])
def transcribe():
    global current_video_path
    if "video" not in request.files:
        return jsonify({"error": "파일이 없어요"}), 400
    file = request.files["video"]
    filename = file.filename or "video.mp4"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)
    current_video_path = os.path.abspath(save_path)
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        with open(current_video_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ko",
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )
        segments = []
        for seg in transcript.segments:
            segments.append({"id": seg.id, "start": round(seg.start, 2), "end": round(seg.end, 2), "text": seg.text.strip()})
        return jsonify({"segments": segments, "video_path": current_video_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get-video-path", methods=["GET"])
def get_video_path():
    return jsonify({"video_path": current_video_path})

@app.route('/analyze-flow', methods=['POST'])
def analyze_flow():
    global current_video_path
    data = request.json
    segments = data.get('segments', [])
    if not segments:
        return jsonify({'error': '자막이 없어요'}), 400

    style_prompt, bgm_keywords, sfx_keywords = get_combined_style()

    transcript_text = ""
    for seg in segments:
        transcript_text += "[" + str(seg['start']) + "초~" + str(seg['end']) + "초] " + seg['text'] + "\n"

    try:
        prompt = """
당신은 브이로그 편집 전문가입니다.

목표 유튜버 스타일:
""" + style_prompt + """

아래는 이 영상의 자막입니다:
""" + transcript_text + """

이 영상을 직접 보면서 아래 기준으로 편집 가이드를 만들어주세요:

1. 흐름이 끊기거나 늘어지는 구간 → delete
2. 개그/황당한 순간 → gag
3. BGM 볼륨을 올려야 할 무음/이동 구간 → bgm_up
4. 유지해야 할 좋은 구간 → keep

영상을 직접 보고 분석하세요:
- 표정, 행동, 배경 등 시각적 요소 반영
- 말 없는 구간에서 무슨 일이 일어나는지 파악
- 개그 포인트는 표정/상황/반응까지 고려

반드시 JSON으로만 답하세요:
{
  "cuts": [
    {"start": 시작초, "end": 끝초, "reason": "이유 (시각적 요소 포함)", "type": "delete/keep/gag/bgm_up", "confidence": "high/medium"}
  ],
  "summary": "전체 흐름 총평",
  "edit_order": ["편집 순서 1", "편집 순서 2", "편집 순서 3"],
  "bgm_recommendations": [
    {"mood": "무드명", "artlist_keywords": ["키워드 1개"], "reason": "이유"}
  ],
  "sfx_recommendations": [
    {"scene": "장면 설명 (표정/행동 포함)", "artlist_keywords": ["키워드 1개"], "timestamp": 시작초}
  ]
}
BGM은 최대 2개, 효과음은 최대 3개만 추천해주세요.
"""
        # 영상 파일이 있으면 Gemini에 직접 업로드해서 분석
        if current_video_path and os.path.exists(current_video_path):
            import time as _time
            uploaded_file = gemini_client.files.upload(file=current_video_path)
            for _ in range(20):
                file_info = gemini_client.files.get(name=uploaded_file.name)
                if file_info.state.name == "ACTIVE":
                    break
                _time.sleep(2)
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[file_info, prompt]
            )
        else:
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text.strip())
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/bgm-list', methods=['GET'])
def bgm_list():
    files = []
    supported = ['.mp3', '.wav', '.m4a', '.aac', '.flac']
    if os.path.exists(BGM_FOLDER):
        for f in os.listdir(BGM_FOLDER):
            if os.path.splitext(f)[1].lower() in supported:
                files.append({'name': os.path.splitext(f)[0], 'file': f})
    return jsonify({'bgms': files})

@app.route('/bgm/<filename>')
def serve_bgm(filename):
    return send_from_directory(BGM_FOLDER, filename)

@app.route('/apply-bgm', methods=['POST'])
def apply_bgm():
    data = request.json
    video_path = data.get('video_path')
    bgm_file = data.get('bgm_file')
    segments = data.get('segments', [])
    bgm_volume = float(data.get('bgm_volume', 0.25))
    duck_volume = float(data.get('duck_volume', 0.05))

    if not video_path or not bgm_file:
        return jsonify({'error': '영상과 BGM을 선택해주세요'}), 400

    bgm_path = os.path.join(BGM_FOLDER, bgm_file)
    if not os.path.exists(bgm_path):
        return jsonify({'error': 'BGM 파일을 찾을 수 없어요'}), 400

    try:
        output_path = os.path.join(tempfile.gettempdir(), 'output_with_bgm.mp4')
        volume_filter = f"[1:a]volume={bgm_volume}"
        for seg in segments:
            volume_filter += f",volume=enable='between(t,{seg['start']},{seg['end']})':volume={duck_volume}"
        filter_complex = f"{volume_filter}[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]"
        cmd = ['ffmpeg', '-y', '-i', video_path, '-stream_loop', '-1', '-i', bgm_path,
               '-filter_complex', filter_complex, '-map', '0:v', '-map', '[aout]',
               '-c:v', 'copy', '-c:a', 'aac', '-shortest', output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return jsonify({'error': 'FFmpeg 오류: ' + result.stderr[-500:]}), 500
        return jsonify({'success': True, 'output_path': output_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/cut-video', methods=['POST'])
def cut_video():
    data = request.json
    video_path = data.get('video_path')
    cuts = data.get('cuts', [])
    if not video_path:
        return jsonify({'error': '영상 경로가 없어요'}), 400
    delete_segments = [c for c in cuts if c['type'] == 'delete']
    if not delete_segments:
        return jsonify({'error': '삭제할 구간이 없어요'}), 400
    try:
        probe_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', video_path]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        duration = float(json.loads(probe_result.stdout)['format']['duration'])
        delete_times = sorted([(c['start'], c['end']) for c in delete_segments])
        keep_segments = []
        current = 0.0
        for start, end in delete_times:
            if current < start:
                keep_segments.append((current, start))
            current = end
        if current < duration:
            keep_segments.append((current, duration))
        if not keep_segments:
            return jsonify({'error': '유지할 구간이 없어요'}), 400
        temp_files = []
        for i, (start, end) in enumerate(keep_segments):
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            tmp.close()
            cmd = ['ffmpeg', '-y', '-i', video_path, '-ss', str(start), '-to', str(end), '-c', 'copy', tmp.name]
            subprocess.run(cmd, capture_output=True)
            temp_files.append(tmp.name)
        list_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w', encoding='utf-8')
        for f in temp_files:
            list_file.write(f"file '{f}'\n")
        list_file.close()
        output_path = os.path.join(tempfile.gettempdir(), 'output_cut.mp4')
        concat_cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_file.name, '-c', 'copy', output_path]
        result = subprocess.run(concat_cmd, capture_output=True, text=True)
        for f in temp_files:
            os.unlink(f)
        os.unlink(list_file.name)
        if result.returncode != 0:
            return jsonify({'error': 'FFmpeg 오류: ' + result.stderr[-500:]}), 500
        return jsonify({'success': True, 'output_path': output_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save-video', methods=['POST'])
def save_video():
    data = request.json
    source_path = data.get('source_path')
    save_name = data.get('save_name', 'vlogcut_output.mp4')
    if not source_path or not os.path.exists(source_path):
        return jsonify({'error': '저장할 파일이 없어요'}), 400
    downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
    output_path = os.path.join(downloads, save_name)
    import shutil
    shutil.copy2(source_path, output_path)
    return jsonify({'success': True, 'saved_to': output_path})


@app.route('/silent-subtitles', methods=['POST'])
def silent_subtitles():
    global current_video_path
    data = request.json
    segments = data.get('segments', [])
    duration = data.get('duration', 0)

    if not current_video_path or not os.path.exists(current_video_path):
        return jsonify({'error': '영상을 먼저 업로드해주세요'}), 400

    # 무음 구간 찾기
    silent_gaps = []
    prev_end = 0.0
    min_gap = 1.5  # 1.5초 이상 무음이면 감지

    for seg in segments:
        if seg['start'] - prev_end >= min_gap:
            silent_gaps.append({'start': round(prev_end, 2), 'end': round(seg['start'], 2)})
        prev_end = seg['end']

    if duration > 0 and duration - prev_end >= min_gap:
        silent_gaps.append({'start': round(prev_end, 2), 'end': round(duration, 2)})

    if not silent_gaps:
        return jsonify({'subtitles': [], 'message': '무음 구간이 없어요!'})

    # Gemini에 영상 업로드 후 분석
    try:
        style_prompt, _, _ = get_combined_style()

        # 영상 파일 Gemini에 업로드 후 ACTIVE 상태 대기
        uploaded_file = gemini_client.files.upload(file=current_video_path)
        # ACTIVE 상태가 될 때까지 대기
        import time as _time
        for _ in range(20):
            file_info = gemini_client.files.get(name=uploaded_file.name)
            if file_info.state.name == "ACTIVE":
                break
            _time.sleep(2)
        else:
            return jsonify({"error": "파일 처리 시간이 초과됐어요. 다시 시도해주세요."}), 500
        uploaded_file = file_info

        gaps_text = ""
        for g in silent_gaps:
            gap_dur = round(g["end"] - g["start"], 1)
            gaps_text += "- " + str(g["start"]) + "초 ~ " + str(g["end"]) + "초 (" + str(gap_dur) + "초 동안 무음)\n"

        prompt = f"""
이 브이로그 영상의 무음 구간들을 보고, 각 구간에 어울리는 센스 있는 자막을 제안해주세요.

목표 유튜버 스타일:
{style_prompt}

무음 구간 목록:
{gaps_text}

자막 스타일 가이드:
- 모하비처럼 잔잔하고 감성적인 상황 묘사
- 예디처럼 황당하거나 웃긴 상황엔 텐션 있게
- 걍밍경처럼 센스 있는 괄호 표현 활용
- 이모지 1-2개 자연스럽게 포함
- 예시: "(드디어 도착...🧸)", "(말 없이 행복한 시간)", "(어...?)", "(이게 맞나...🤔)"

각 무음 구간마다 자막 제안을 해주세요.
반드시 JSON으로만 답하세요:
{{
  "subtitles": [
    {{"start": 시작초, "end": 끝초, "text": "제안 자막", "reason": "이 자막을 제안한 이유"}}
  ]
}}
"""
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[uploaded_file, prompt]
        )

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        result = json.loads(text.strip())
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
