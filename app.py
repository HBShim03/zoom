import streamlit as st
import pandas as pd
import csv
import unicodedata
import re
from collections import defaultdict
import io

# 💡 페이지 기본 설정 (가장 위에 있어야 함)
st.set_page_config(page_title="Zoom CSV Grouper", page_icon="📊", layout="wide")

def clean_text(text):
    """Mac의 쪼개진 한글(NFD)을 정상(NFC)으로 합치고 특수문자를 제거합니다."""
    normalized = unicodedata.normalize('NFC', text)
    return re.sub(r'[^가-힣a-zA-Z]', '', normalized).lower()

def process_zoom_csv(file_content, hourly_rate):
    lines = []
    encodings = ['utf-8', 'euc-kr', 'cp949']
    
    # 바이트(bytes) 데이터를 문자열로 디코딩
    for enc in encodings:
        try:
            text_data = file_content.decode(enc)
            # csv.reader는 파일 객체나 리스트 형태의 문자열을 받으므로 io.StringIO 사용
            reader = csv.reader(io.StringIO(text_data))
            lines = list(reader)
            break
        except UnicodeDecodeError:
            continue

    if not lines:
        return {"error": "파일을 읽을 수 없거나 인코딩 형식이 맞지 않습니다."}

    header_idx = -1
    name_idx = date_idx = duration_idx = waiting_room_idx = -1

    for i, row in enumerate(lines[:10]):
        for j, col in enumerate(row):
            c = clean_text(col)
            if '이름' in c or 'name' in c: name_idx = j
            elif '참가시간' in c or 'jointime' in c: date_idx = j
            elif '대기실에서' in c or 'waitingroom' in c: waiting_room_idx = j
                
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
        return {"error": "필수 항목(이름, 참가시간, 기간)을 찾지 못했습니다."}

    results = []
    participant_summary = defaultdict(int)
    total_host_earnings = 0

    for i in range(header_idx + 1, len(lines)):
        row = lines[i]
        if len(row) <= max(name_idx, date_idx, duration_idx): continue

        if waiting_room_idx != -1 and waiting_room_idx < len(row):
            waiting_val = unicodedata.normalize('NFC', row[waiting_room_idx].strip())
            if waiting_val == '예' or waiting_val.lower() == 'yes':
                continue

        name = unicodedata.normalize('NFC', row[name_idx].strip())
        raw_date = row[date_idx].strip()
        raw_duration = row[duration_idx].strip() if duration_idx < len(row) else "0"

        if not name or not raw_date: continue

        try:
            duration_val = int(raw_duration)
        except ValueError:
            continue

        # +-10분 오차 보정
        if 50 <= duration_val <= 70: standard_duration = 60
        elif 80 <= duration_val <= 100: standard_duration = 90
        elif 110 <= duration_val <= 130: standard_duration = 120
        else: continue

        date_only = raw_date.split(' ')[0]
        parts = re.split(r'[/\\-]', date_only)
        formatted_date = raw_date
        if len(parts) >= 2:
            m = int(parts[1] if len(parts) == 3 else parts[0])
            d = int(parts[2] if len(parts) == 3 else parts[1])
            formatted_date = f"{m}/{d}"

        # 수익 계산
        earnings = int((standard_duration / 60.0) * hourly_rate)

        results.append({
            "연번": 0, # 나중에 채움
            "참가자 이름 (Participant)": name,
            "참여 날짜 (Date)": formatted_date,
            "보정된 기간(분)": standard_duration,
            "수익(원)": f"{earnings:,}" # 천 단위 콤마 추가
        })

        participant_summary[name] += earnings
        if name.lower().endswith('(host)'):
            total_host_earnings += earnings

    if not results:
        return {"error": "추출할 데이터가 없습니다. (시간 외 데이터이거나 대기실만 존재)"}

    # 이름 순 정렬 및 연번 매기기
    results.sort(key=lambda x: x["참가자 이름 (Participant)"])
    for idx, row in enumerate(results, start=1):
        row["연번"] = idx

    return {
        "data": results,
        "total_earnings": total_host_earnings,
        "summary": participant_summary
    }

# --- 💡 Streamlit UI 구성 ---

st.title("Zoom meeting CSV Grouper & Earnings Calculator")
st.markdown("Zoom 회의 기록 CSV 파일을 업로드하면 **오차 보정 및 참가자별 수익**을 자동으로 계산해 줍니다.")
st.markdown("*(50~70분은 60분으로 자동 보정되며, 대기실에만 머문 사용자는 제외됩니다.)*")
st.divider()

# 레이아웃 나누기 (좌측: 입력부 / 우측: 요약부)
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 설정 및 업로드")
    hourly_rate = st.number_input("💸 시급(Hourly Rate)을 입력하세요 (원)", min_value=0, value=60000, step=1000)
    uploaded_file = st.file_uploader("📁 Zoom CSV 파일 업로드", type=['csv'])

if uploaded_file is not None:
    # 파일을 바이트 형태로 읽어옴
    file_bytes = uploaded_file.getvalue()
    result = process_zoom_csv(file_bytes, hourly_rate)

    if "error" in result:
        st.error(result["error"])
    else:
        # 데이터프레임으로 변환하여 표출
        df = pd.DataFrame(result["data"])
        
        with col2:
            st.subheader("2. 수익 요약")
            st.success(f"**예상 총 수익: {result['total_earnings']:,} 원**")
            
            with st.expander("참가자별 누적 수익 보기", expanded=True):
                for name, earned in sorted(result["summary"].items(), key=lambda x: x[0]):
                    st.write(f"• **{name}**: {earned:,} 원")

        st.divider()
        st.subheader("3. 개별 회의 기록 (상세)")
        # 웹사이트에서 예쁜 표(데이터프레임)로 출력
        st.dataframe(df, use_container_width=True, hide_index=True)