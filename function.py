import csv
import unicodedata
import re
from collections import defaultdict

def clean_text(text):
    """Mac의 쪼개진 한글(NFD)을 정상(NFC)으로 합치고 특수문자를 제거합니다."""
    normalized = unicodedata.normalize('NFC', text)
    return re.sub(r'[^가-힣a-zA-Z]', '', normalized).lower()

def process_zoom_csv(file_path):
    # 1. 인코딩 자동 감지
    encodings = ['utf-8', 'euc-kr', 'cp949']
    lines = []
    
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                reader = csv.reader(f)
                lines = list(reader)
            break
        except UnicodeDecodeError:
            continue

    if not lines:
        print("파일을 읽을 수 없거나 파일이 비어있습니다.")
        return

    header_idx = -1
    name_idx = date_idx = duration_idx = waiting_room_idx = -1  # 대기실 인덱스 추가

    # 2. 헤더(항목 이름) 찾기
    for i, row in enumerate(lines[:10]):
        for j, col in enumerate(row):
            c = clean_text(col)
            if '이름' in c or 'name' in c:
                name_idx = j
            elif '참가시간' in c or 'jointime' in c:
                date_idx = j
            elif '대기실에서' in c or 'waitingroom' in c:  # <-- 대기실 항목 위치 찾기
                waiting_room_idx = j
                
        # 기간 찾기
        if name_idx != -1:
            for j in range(name_idx, len(row)):
                c = clean_text(row[j])
                if '기간' in c or 'duration' in c:
                    duration_idx = j
                    break

        if name_idx != -1 and date_idx != -1 and duration_idx != -1:
            header_idx = i
            break

    if header_idx == -1:
        print("오류: 필수 항목(이름, 참가시간, 기간)을 찾지 못했습니다.")
        return

    # 3. 데이터 그룹화
    grouped_data = defaultdict(lambda: {'dates': [], 'durations': []})

    for i in range(header_idx + 1, len(lines)):
        row = lines[i]
        if len(row) <= max(name_idx, date_idx, duration_idx):
            continue

        # ✨ [필터링 추가] '대기실에서'가 '예'인 경우 이 행을 건너뜀(제외)
        if waiting_room_idx != -1 and waiting_room_idx < len(row):
            waiting_val = unicodedata.normalize('NFC', row[waiting_room_idx].strip())
            if waiting_val == '예' or waiting_val.lower() == 'yes':
                continue

        name = unicodedata.normalize('NFC', row[name_idx].strip())
        raw_date = row[date_idx].strip()
        duration = row[duration_idx].strip() if duration_idx < len(row) else "0"

        if not name or not raw_date:
            continue

        # "2026/03/30 09:59:00 AM" 형식에서 "3/30" 추출
        date_only = raw_date.split(' ')[0]
        parts = re.split(r'[/\\-]', date_only)
        formatted_date = raw_date
        if len(parts) >= 2:
            m = int(parts[1] if len(parts) == 3 else parts[0])
            d = int(parts[2] if len(parts) == 3 else parts[1])
            formatted_date = f"{m}/{d}"

        grouped_data[name]['dates'].append(formatted_date)
        grouped_data[name]['durations'].append(duration)

    # 4. 결과 출력
    if not grouped_data:
        print("추출할 데이터가 없습니다.")
        return

    count = 1
    for name, info in grouped_data.items():
        print(f"Participant Name {count}: {name}")
        print(f"Meeting date: {', '.join(info['dates'])}")
        print(f"Meeting duration: {', '.join(info['durations'])}\n")
        count += 1

# ===== 실행 부분 =====
csv_filename = "/Users/hanboshim/Downloads/meeting_summary/meetinglistdetails_2026_03_01_2026_03_31 (1).csv" 
process_zoom_csv(csv_filename)