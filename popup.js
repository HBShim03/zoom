document.getElementById('processBtn').addEventListener('click', () => {
    const fileInput = document.getElementById('csvFileInput');
    if (fileInput.files.length === 0) {
        alert('CSV 파일을 먼저 선택해주세요.');
        return;
    }

    const file = fileInput.files[0];
    
    readFile(file, 'utf-8', (text) => {
        let result = processCSV(text);
        
        if (!result.success && text.includes('')) {
            console.log("UTF-8 실패, EUC-KR로 재시도합니다...");
            readFile(file, 'euc-kr', (text2) => {
                let result2 = processCSV(text2);
                if (!result2.success) {
                    document.getElementById('output').textContent = result2.msg;
                }
            });
        } else if (!result.success) {
            document.getElementById('output').textContent = result.msg;
        }
    });
});

function readFile(file, encoding, callback) {
    const reader = new FileReader();
    reader.onload = function(e) {
        callback(e.target.result);
    };
    reader.readAsText(file, encoding);
}

function parseCSVLine(text) {
    let result = [];
    let curVal = '';
    let inQuotes = false;
    for (let i = 0; i < text.length; i++) {
        let char = text[i];
        if (inQuotes) {
            if (char === '"') {
                if (i < text.length - 1 && text[i+1] === '"') {
                    curVal += '"';
                    i++;
                } else {
                    inQuotes = false;
                }
            } else {
                curVal += char;
            }
        } else {
            if (char === '"') {
                inQuotes = true;
            } else if (char === ',') {
                result.push(curVal.trim());
                curVal = '';
            } else {
                curVal += char;
            }
        }
    }
    result.push(curVal.trim());
    return result;
}

function processCSV(csvText) {
    const lines = csvText.split(/\r?\n/).filter(line => line.trim() !== '');
    if (lines.length === 0) return { success: false, msg: "오류: 파일이 비어있습니다." };
    let headerLineIdx = -1;
    let nameIdx = -1, dateIdx = -1, durationIdx = -1;
    let detectedHeaders = "";

    function headerIndexByPatterns(headers, patterns) {
        for (let i = 0; i < headers.length; i++) {
            const clean = headers[i].normalize('NFC').replace(/\s/g, '').toLowerCase();
            for (const p of patterns) {
                if (typeof p === 'string') {
                    if (clean.includes(p)) return i;
                } else if (p instanceof RegExp) {
                    if (p.test(clean)) return i;
                }
            }
        }
        return -1;
    }

    for (let i = 0; i < Math.min(lines.length, 10); i++) {
        const currentLineHeaders = parseCSVLine(lines[i]);
        if (i === 0) detectedHeaders = currentLineHeaders.join(' | ');

        nameIdx = headerIndexByPatterns(currentLineHeaders, ['이름(원래', '참가자', '참가자이름', '이름', 'name']);

        dateIdx = headerIndexByPatterns(currentLineHeaders, ['참가시간', '참가', 'jointime', '시작시간', 'starttime']);

        if (nameIdx !== -1) {
            for (let j = nameIdx; j < currentLineHeaders.length; j++) {
                const clean = currentLineHeaders[j].normalize('NFC').replace(/\s/g, '').toLowerCase();
                if (clean.includes('기간(분)') || clean.includes('기간') || clean.includes('duration')) {
                    durationIdx = j;
                    break;
                }
            }
        }

        if (durationIdx === -1) {
            durationIdx = headerIndexByPatterns(currentLineHeaders, ['기간(분)', '기간', 'duration']);
        }

        if (nameIdx !== -1 && dateIdx !== -1 && durationIdx !== -1) {
            headerLineIdx = i;
            break;
        }
    }

    if (headerLineIdx === -1) {
        return { 
            success: false, 
            msg: `오류: 필수 항목을 찾지 못했습니다.\n\n[프로그램이 읽어낸 첫 번째 줄 데이터]\n${detectedHeaders}` 
        };
    }

    const groupedData = {};

    for (let i = headerLineIdx + 1; i < lines.length; i++) {
        const row = parseCSVLine(lines[i]);

        if (row.length <= Math.max(nameIdx, dateIdx, durationIdx)) continue;

        const name = row[nameIdx] ? row[nameIdx].normalize('NFC').replace(/\r/g, '') : "";
        const rawDate = row[dateIdx] ? row[dateIdx].replace(/\r/g, '') : "";
        let duration = row[durationIdx] ? row[durationIdx].replace(/\r/g, '') : "0";

        if (!name || !rawDate) continue;

        let formattedDate = rawDate;
        const dateOnly = rawDate.split(' ')[0]; 
        if (dateOnly) {
            const parts = dateOnly.includes('/') ? dateOnly.split('/') : dateOnly.split('-');
            if (parts.length >= 2) {
                const m = parseInt(parts[parts.length === 3 ? 1 : 0], 10);
                const d = parseInt(parts[parts.length === 3 ? 2 : 1], 10);
                if (!isNaN(m) && !isNaN(d)) formattedDate = `${m}/${d}`;
            }
        }

        if (!groupedData[name]) {
            groupedData[name] = { dates: [], durations: [] };
        }

        groupedData[name].dates.push(formattedDate);
        groupedData[name].durations.push(duration);
    }

    displayOutput(groupedData);
    return { success: true };
}

function displayOutput(data) {
    let outputText = "";
    let count = 1;
    let hasData = false;

    for (const [name, info] of Object.entries(data)) {
        hasData = true;
        outputText += `Participant Name ${count}: ${name}\n`;
        outputText += `Meeting date: ${info.dates.join(', ')}\n`;
        outputText += `Meeting duration: ${info.durations.join(', ')}\n\n`;
        count++;
    }

    if (!hasData) {
         document.getElementById('output').textContent = "추출할 데이터가 없습니다.";
    } else {
         document.getElementById('output').textContent = outputText.trim();
    }
}