import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import csv
import unicodedata
import re
from collections import defaultdict

def clean_text(text):
    """Mac의 쪼개진 한글(NFD)을 정상(NFC)으로 합치고 특수문자를 제거합니다."""
    normalized = unicodedata.normalize('NFC', text)
    return re.sub(r'[^가-힣a-zA-Z]', '', normalized).lower()

def process_zoom_csv(file_path, hourly_rate):
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
        return {"error": "오류: 파일을 읽을 수 없거나 파일이 비어있습니다."}

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
        return {"error": "오류: 필수 항목(이름, 참가시간, 기간)을 찾지 못했습니다."}

    results = []
    participant_summary = defaultdict(int)
    total_host_earnings = 0

    for i in range(header_idx + 1, len(lines)):
        row = lines[i]
        if len(row) <= max(name_idx, date_idx, duration_idx): continue

        # 대기실에서 '예'인 경우 제외
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

        # ✨ +-10분 오차 보정 및 규격 외 시간 제외
        if 50 <= duration_val <= 70: standard_duration = 60
        elif 80 <= duration_val <= 100: standard_duration = 90
        elif 110 <= duration_val <= 130: standard_duration = 120
        else: continue

        # 날짜 포맷팅
        date_only = raw_date.split(' ')[0]
        parts = re.split(r'[/\\-]', date_only)
        formatted_date = raw_date
        if len(parts) >= 2:
            m = int(parts[1] if len(parts) == 3 else parts[0])
            d = int(parts[2] if len(parts) == 3 else parts[1])
            formatted_date = f"{m}/{d}"

        # 💡 해당 세션(Row)의 수익 계산
        earnings = int((standard_duration / 60.0) * hourly_rate)

        results.append({
            "name": name,
            "date": formatted_date,
            "duration": standard_duration,
            "earnings": earnings
        })

        # ✨ 참가자별 총 수익 누적
        participant_summary[name] += earnings
        
        # 이름이 (Host)로 끝나는 데이터의 경우 호스트 총 수익에도 누적
        if name.lower().endswith('(host)'):
            total_host_earnings += earnings

    if not results:
        return {"error": "추출할 데이터가 없습니다. (지정된 시간 외의 항목이거나 대기실 데이터만 존재)"}

    # 이름 순으로 정렬
    results.sort(key=lambda x: x["name"])

    return {
        "data": results, 
        "earnings": total_host_earnings,
        "participant_summary": participant_summary
    }


# --- GUI Application Setup ---
def open_file():
    try:
        rate_str = rate_entry.get().replace(",", "").strip()
        if not rate_str:
            messagebox.showwarning("입력 필요", "시급(Hourly Rate)을 먼저 입력해주세요.")
            return
        hourly_rate = int(rate_str)
    except ValueError:
        messagebox.showerror("입력 오류", "시급은 숫자만 입력 가능합니다.")
        return

    file_path = filedialog.askopenfilename(
        title="Zoom CSV 파일 선택",
        filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
    )
    if file_path:
        try:
            for item in tree.get_children():
                tree.delete(item)
                
            result = process_zoom_csv(file_path, hourly_rate)
            
            if "error" in result:
                messagebox.showerror("오류", result["error"])
                earnings_var.set("총 수익: 0 원")
                summary_text.config(state=tk.NORMAL)
                summary_text.delete(1.0, tk.END)
                summary_text.config(state=tk.DISABLED)
            else:
                # 표에 데이터(수익 포함) 삽입
                for idx, row in enumerate(result["data"], start=1):
                    tree.insert("", tk.END, values=(idx, row["name"], row["date"], row["duration"], f"{row['earnings']:,}"))
                
                # 호스트 총 수익 표출
                earnings_var.set(f"예상 총 수익: {result['earnings']:,} 원")

                # ✨ 하단에 참가자별 누적 수익 요약 표출
                summary_text.config(state=tk.NORMAL)
                summary_text.delete(1.0, tk.END)
                summary_text.insert(tk.END, "[참가자별 누적 수익 요약]\n")
                summary_text.insert(tk.END, "-" * 40 + "\n")
                
                # 가나다/ABC 순으로 정렬하여 출력
                for name, earned in sorted(result["participant_summary"].items(), key=lambda x: x[0]):
                    summary_text.insert(tk.END, f" • {name}: {earned:,} 원\n")
                    
                summary_text.config(state=tk.DISABLED)
                    
        except Exception as e:
            messagebox.showerror("오류", f"알 수 없는 오류가 발생했습니다:\n{str(e)}")

# 메인 창 생성
root = tk.Tk()
root.title("Zoom CSV Parser (오차 보정 및 참가자별 수익 계산)")
root.geometry("800x750") # 레이아웃 최적화를 위해 높이/너비 증가
root.configure(padx=20, pady=10)

# 안내 문구
lbl = tk.Label(root, text="시급을 입력하고 Zoom CSV 파일을 업로드해주세요.\n(50~70분은 60분으로 자동 보정되며, 참가자별 수익이 모두 계산됩니다.)", font=("Arial", 11))
lbl.pack(pady=(0, 10))

# 시급 입력 영역
rate_frame = tk.Frame(root)
rate_frame.pack(pady=5)

tk.Label(rate_frame, text="시급(Hourly Rate):", font=("Arial", 11, "bold")).pack(side=tk.LEFT)
rate_entry = tk.Entry(rate_frame, font=("Arial", 11), width=12)
rate_entry.pack(side=tk.LEFT, padx=5)
tk.Label(rate_frame, text="원", font=("Arial", 11)).pack(side=tk.LEFT)

# 버튼
btn = tk.Button(root, text="📁 CSV 파일 선택 및 처리", command=open_file, font=("Arial", 11, "bold"), bg="#4CAF50", fg="black", padx=10, pady=5)
btn.pack(pady=5)

# 표(Table) 영역 생성
table_frame = tk.Frame(root)
table_frame.pack(expand=True, fill=tk.BOTH, pady=(5, 5))

scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# 💡 수익(Earnings) 열 추가
columns = ("No", "Name", "Date", "Duration", "Earnings")
tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10, yscrollcommand=scrollbar.set)
scrollbar.config(command=tree.yview)

tree.heading("No", text="연번")
tree.column("No", width=40, anchor=tk.CENTER)
tree.heading("Name", text="참가자 이름 (Participant)")
tree.column("Name", width=180, anchor=tk.W)
tree.heading("Date", text="참여 날짜")
tree.column("Date", width=100, anchor=tk.CENTER)
tree.heading("Duration", text="보정된 기간(분)")
tree.column("Duration", width=100, anchor=tk.CENTER)
tree.heading("Earnings", text="수익(원)")       # 추가된 부분
tree.column("Earnings", width=100, anchor=tk.E) # 금액이므로 우측(E) 정렬

tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

# 총 수익 표출 라벨
earnings_var = tk.StringVar()
earnings_var.set("예상 총 수익: 0 원")
earnings_label = tk.Label(root, textvariable=earnings_var, font=("Arial", 14, "bold"), fg="white", bg="#4CAF50", padx=10, pady=5)
earnings_label.pack(pady=(5, 5))

# 💡 참가자별 총 수익 요약 텍스트 박스 추가
summary_text = tk.Text(root, height=7, font=("Consolas", 11), fg="black", bg="#f9f9f9", relief=tk.GROOVE, borderwidth=2)
summary_text.pack(fill=tk.X, pady=(5, 10))
summary_text.insert(tk.END, "파일을 업로드하면 이곳에 참가자별 누적 수익 요약이 표시됩니다.")
summary_text.config(state=tk.DISABLED) # 읽기 전용

root.mainloop()