from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import base64, math

OUT = Path(r'D:\Magang Telkomsel\FUT\fut-ai-automation-main\fut-ai-automation-main\figma-api-playground\docs')
OUT.mkdir(parents=True, exist_ok=True)
W, H = 2200, 3300
img = Image.new('RGB', (W, H), '#fbfbf7')
d = ImageDraw.Draw(img)

def font(size, bold=False):
    paths = [r'C:\Windows\Fonts\arialbd.ttf' if bold else r'C:\Windows\Fonts\arial.ttf', r'C:\Windows\Fonts\segoeuib.ttf' if bold else r'C:\Windows\Fonts\segoeui.ttf']
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

F_TITLE = font(48, True)
F_SUB = font(25)
F_SECTION = font(28, True)
F_BOX_TITLE = font(20, True)
F_BOX = font(17)
F_SMALL = font(15)
F_NUM = font(26, True)
F_FOOTER = font(16)
F_FOOTER_B = font(18, True)

COL = {
    'navy':'#06375e', 'ink':'#19202a', 'muted':'#5f6b7a', 'line':'#24303d',
    'blue':'#e8f3ff', 'blue_s':'#1b67a7',
    'green':'#eaf8ee', 'green_s':'#26834a',
    'yellow':'#fff7dc', 'yellow_s':'#c99319',
    'purple':'#f4edff', 'purple_s':'#7a49a5',
    'orange':'#fff0df', 'orange_s':'#dc7622',
    'red':'#ffe8e8', 'red_s':'#cc4040',
    'gray':'#f6f7f9', 'gray_s':'#9aa5b1',
    'white':'#ffffff'
}

def bbox(text, f):
    b = d.textbbox((0, 0), text, font=f)
    return b[2] - b[0], b[3] - b[1]

def wrap_px(text, f, max_w):
    lines = []
    for para in str(text).split('\n'):
        words = para.split()
        if not words:
            lines.append('')
            continue
        line = ''
        for word in words:
            cand = word if not line else line + ' ' + word
            if bbox(cand, f)[0] <= max_w:
                line = cand
            else:
                if line:
                    lines.append(line)
                    line = word
                else:
                    lines.append(word)
                    line = ''
        if line:
            lines.append(line)
    return lines

def draw_wrapped(x, y, w, text, f, fill=COL['ink'], line_gap=6, max_lines=None):
    lines = wrap_px(text, f, w)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip('.') + '...'
    yy = y
    for line in lines:
        d.text((x, yy), line, font=f, fill=fill)
        yy += bbox(line or 'A', f)[1] + line_gap
    return yy

def draw_center(x1, y1, x2, y2, text, f, fill=COL['ink'], line_gap=6):
    lines = wrap_px(text, f, max(20, x2-x1-20))
    total = sum(bbox(line or 'A', f)[1] for line in lines) + line_gap * (len(lines)-1)
    yy = y1 + (y2-y1-total)/2
    for line in lines:
        tw, th = bbox(line, f)
        d.text((x1 + (x2-x1-tw)/2, yy), line, font=f, fill=fill)
        yy += th + line_gap

def rounded(x1,y1,x2,y2, fill, stroke, r=18, width=2):
    d.rounded_rectangle((x1,y1,x2,y2), radius=r, fill=fill, outline=stroke, width=width)

def arrow(x1,y1,x2,y2, fill=COL['line'], width=3):
    d.line((x1,y1,x2,y2), fill=fill, width=width)
    ang = math.atan2(y2-y1, x2-x1)
    length = 16
    pts = [(x2,y2), (x2-length*math.cos(ang-0.48), y2-length*math.sin(ang-0.48)), (x2-length*math.cos(ang+0.48), y2-length*math.sin(ang+0.48))]
    d.polygon(pts, fill=fill)

def box(x,y,w,h,title,body, fill=COL['white'], stroke=COL['gray_s'], tag=None):
    rounded(x,y,x+w,y+h,fill,stroke,14,2)
    if tag:
        d.rounded_rectangle((x+18,y+18,x+74,y+48), radius=8, fill=stroke, outline=stroke)
        draw_center(x+18,y+18,x+74,y+48,tag,font(14,True),'white')
        title_x = x+88
    else:
        title_x = x+20
    d.text((title_x, y+20), title, font=F_BOX_TITLE, fill=COL['ink'])
    draw_wrapped(x+20, y+60, w-40, body, F_BOX, COL['ink'], line_gap=6, max_lines=5)

def section(y, h, num, title, fill, stroke):
    x, w = 36, 1700
    rounded(x,y,x+w,y+h,fill,stroke,16,2)
    d.rectangle((x,y,x+54,y+54), fill=stroke)
    draw_center(x,y,x+54,y+54,str(num),F_NUM,'white')
    d.text((x+76,y+18), title, font=F_SECTION, fill=stroke)
    return x, y, w, h

# Header
rounded(24, 24, W-24, 142, COL['navy'], COL['navy'], 28, 1)
draw_center(24, 36, W-24, 86, 'FLOWCHART FUT AI AUTOMATION', F_TITLE, 'white')
draw_center(24, 88, W-24, 128, 'Business Process with Figma API Playground Integration', F_SUB, 'white')

# Top login flow
rounded(90,230,230,305,'#e8f8dc','#3b8d45',36,2); draw_center(90,230,230,305,'START',F_BOX_TITLE)
box(430,200,300,140,'1. LOGIN','User memasukkan username dan password.', '#e8f4ff', '#4f86ba', 'AUTH')
# Decision diamond
cx, cy = 970, 270
d.polygon([(cx,cy-82),(cx+105,cy),(cx,cy+82),(cx-105,cy)], fill='#fff3ca', outline='#b99d35')
draw_center(cx-70,cy-50,cx+70,cy+50,'Validasi Login',F_SMALL)
box(1300,200,330,140,'Dashboard','Menampilkan project, knowledge base, dan akses Figma API Playground.', '#e8f8eb', '#4f9b58', 'HOME')
box(850,410,260,115,'Login Gagal','Tampilkan pesan error dan kembali ke form login.', '#ffe8e8', '#cc4040', 'ERR')
arrow(230,267,430,267); arrow(730,267,865,267); arrow(1075,267,1300,267)
draw_center(1120,226,1190,250,'YA',F_BOX_TITLE,'#168a45')
arrow(970,352,970,410); draw_center(990,360,1080,386,'TIDAK',F_BOX_TITLE,'#c73c3c')
arrow(1465,340,1465,540); d.line((1465,540,640,540),fill=COL['line'],width=3); arrow(640,540,640,600)

# Section 1
section(600, 270, 1, 'KELOLA KNOWLEDGE BASE (Historical FUT)', COL['blue'], COL['blue_s'])
box(80,700,300,120,'Upload Historical FUT','Upload dokumen FUT lama sebagai referensi AI.', tag='PDF')
box(500,700,330,120,'Parsing Dokumen','Ekstraksi section, scenario, steps, expected result, status, note.', tag='PARSE')
box(950,700,340,120,'Simpan Knowledge','Data tersimpan ke MongoDB dan file ke GridFS.', tag='DB')
box(1410,700,270,120,'Knowledge Siap','Dipakai sebagai referensi generate dan matching.', '#fffefa', COL['gray_s'], 'READY')
arrow(380,760,500,760); arrow(830,760,950,760); arrow(1290,760,1410,760)

# Section 2
section(910, 430, 2, 'BUAT PROJECT & AMBIL FLOW DARI FIGMA API PLAYGROUND', COL['green'], COL['green_s'])
box(80,1030,295,145,'Buat Project Baru','Isi metadata project: channel, environment, PIC, target, dan coverage.', tag='PRJ')
box(445,1030,310,145,'Figma API Playground','Input token + file key atau gunakan Load Saved lokal.', '#f1fff4', COL['green_s'], 'FIGMA')
box(825,1030,330,145,'Load Struktur Figma','Ambil pages, sections, frames, dan metadata dari Figma API.', tag='API')
box(1225,1030,300,145,'Pilih Section Flow','User memilih section yang merepresentasikan flow FUT.', tag='CHECK')
box(80,1210,335,90,'Fallback Manual','Jika API/rate limit gagal, user tetap bisa upload Figma PDF manual.', '#fff7e6', COL['yellow_s'], 'ALT')
box(620,1210,360,90,'Export Split PDF ZIP','Satu Figma section menjadi satu PDF flow.', '#fffefa', COL['gray_s'], 'ZIP')
box(1185,1210,310,90,'Flow PDF Siap','Dipakai sebagai input generate test case.', '#fffefa', COL['gray_s'], 'READY')
arrow(375,1102,445,1102); arrow(755,1102,825,1102); arrow(1155,1102,1225,1102)
d.line((1375,1175,1375,1255), fill=COL['line'], width=3); arrow(1375,1255,1185,1255)
arrow(415,1255,620,1255); arrow(980,1255,1185,1255)

# Section 3
section(1380, 260, 3, 'GENERATE TEST CASE AI (Dari Split Section PDF)', COL['yellow'], COL['yellow_s'])
box(80,1485,330,115,'Import Flow PDF','ZIP dari Playground berisi file PDF per section.', tag='PDF')
box(535,1485,390,115,'Generate Test Case','AI membaca flow PDF + knowledge base untuk membuat scenario dan steps.', tag='AI')
box(1050,1485,340,115,'Review Test Case','User validasi dan edit sebelum proses testing.', tag='EDIT')
box(1500,1485,180,115,'Test Case Siap','Siap testing dan matching.', '#fffefa', COL['gray_s'], 'OK')
arrow(410,1542,535,1542); arrow(925,1542,1050,1542); arrow(1390,1542,1500,1542)

# Section 4
section(1680, 250, 4, 'UPLOAD SCREENSHOT HASIL TESTING', COL['yellow'], COL['yellow_s'])
box(80,1780,330,110,'Upload Screenshot','Upload gambar hasil testing: PNG, JPG, atau WebP.', tag='IMG')
box(585,1780,360,110,'Simpan Capture','Gambar dan metadata disimpan di MongoDB/GridFS.', tag='DB')
box(1130,1780,300,110,'Screenshot Siap','Siap dianalisis OCR, Vision AI, dan matching.', '#fffefa', COL['gray_s'], 'READY')
arrow(410,1835,585,1835); arrow(945,1835,1130,1835)

# Section 5
section(1970, 390, 5, 'ANALISIS AI: OCR & AUTO MATCHING', COL['purple'], COL['purple_s'])
box(80,2085,270,115,'OCR','Ekstraksi teks dari screenshot testing.', tag='OCR')
box(470,2085,360,115,'Screen Recognition','AI mengenali screen, state, elemen, popup, success/error.', tag='VISION')
box(950,2085,360,115,'Auto Matching','Cocokkan screenshot dengan test case dan expected result.', tag='MATCH')
box(1430,2085,250,115,'Confidence Score','Hitung skor kecocokan 0 sampai 1.', tag='SCORE')
box(470,2245,300,95,'Matched','Screenshot masuk ke test case paling sesuai.', '#e8f8eb', '#3d9b58', 'PASS')
box(1125,2245,360,95,'Unassigned Capture','Jika confidence rendah, masuk review manual.', '#ffe8e8', COL['red_s'], 'REVIEW')
arrow(350,2142,470,2142); arrow(830,2142,950,2142); arrow(1310,2142,1430,2142)
arrow(1115,2200,620,2245,'#2f8f4e'); draw_center(620,2205,925,2238,'Confidence >= threshold',F_SMALL,'#168a45')
arrow(1535,2200,1305,2245,COL['red_s']); draw_center(1260,2205,1570,2238,'Confidence < threshold',F_SMALL,'#c73c3c')

# Section 6
section(2400, 250, 6, 'REVIEW HASIL & UPDATE STATUS', COL['blue'], COL['blue_s'])
box(80,2500,360,110,'Review Matching','Cek screenshot, expected result, actual result, dan confidence.', tag='REVIEW')
box(620,2500,420,110,'Update Status & Note','Set status: PASS, FAIL, BLOCKED, PASS_WITH_NOTE, dll.', tag='STATUS')
box(1220,2500,330,110,'Simpan Hasil','Semua perubahan disimpan ke MongoDB.', tag='SAVE')
arrow(440,2555,620,2555); arrow(1040,2555,1220,2555)

# Section 7
section(2690, 220, 7, 'EXPORT FUT', COL['orange'], COL['orange_s'])
box(80,2785,310,95,'Export PDF','Generate dokumen FUT final dalam format PDF.', tag='PDF')
box(560,2785,330,95,'Export DOCX','Generate dokumen FUT Word yang bisa diedit.', tag='DOCX')
box(1060,2785,335,95,'Dokumen FUT Siap','Siap dibagikan ke stakeholder atau report.', '#fffefa', COL['gray_s'], 'DONE')
rounded(1575,2795,1690,2870,'#e8f8dc','#3b8d45',36,2); draw_center(1575,2795,1690,2870,'END',F_BOX_TITLE)
arrow(390,2832,560,2832); arrow(890,2832,1060,2832); arrow(1395,2832,1575,2832)

# Sidebar
sx, sy, sw, sh = 1780, 600, 380, 2140
rounded(sx, sy, sx+sw, sy+sh, '#ffffff', '#9aa3ad', 18, 2)
draw_center(sx+20, sy+24, sx+sw-20, sy+78, 'KOMPONEN SISTEM', F_BOX_TITLE)
components = [
    ('FRONTEND', 'HTML, CSS, JS\nBootstrap 5\nResponsive UI', '#e8f4ff', 'WEB'),
    ('FIGMA API PLAYGROUND', 'Figma REST API\nSaved token lokal\nSplit section PDF ZIP', '#eaf8ee', 'FIGMA'),
    ('BACKEND', 'Flask / Python\nREST Routes\nBackground Worker', '#fff7dc', 'PY'),
    ('AI SERVICES', 'Groq LLM + Vision\nGenerate test case\nAuto matching', '#f4edff', 'AI'),
    ('DATABASE', 'MongoDB Atlas\nprojects, test_cases\ncaptures, knowledge_docs\nGridFS storage', '#eaf8ee', 'DB'),
    ('OCR ENGINE', 'Tesseract OCR\nVision fallback', '#f6f7f9', 'OCR'),
    ('DEPLOYMENT', 'Render Web Service\nGunicorn\nMongoDB Atlas', '#e8f4ff', 'CLOUD'),
]
y = sy + 110
for title, body, fill, tag in components:
    box(sx+28, y, sw-56, 220, title, body, fill, '#9aa3ad', tag)
    y += 285

# Footer panels
fy = 2980
rounded(36, fy, 830, 3260, 'white', '#b6bdc6', 16, 1)
d.text((64, fy+26), 'KETERANGAN FLOW', font=F_FOOTER_B, fill=COL['ink'])
flow_notes = [
    '1. Historical FUT menjadi knowledge base AI.',
    '2. Figma API Playground mengganti export Figma PDF manual.',
    '3. Satu Figma section diexport menjadi satu PDF flow.',
    '4. PDF flow dipakai AI untuk generate test case.',
    '5. Screenshot hasil testing dicocokkan otomatis.',
    '6. Hasil final diexport ke PDF/DOCX.'
]
yy = fy + 62
for note in flow_notes:
    d.text((64, yy), note, font=F_FOOTER, fill=COL['ink'])
    yy += 34

rounded(870, fy, 1540, 3260, 'white', '#b6bdc6', 16, 1)
d.text((898, fy+26), 'PERUBAHAN UTAMA', font=F_FOOTER_B, fill=COL['ink'])
draw_wrapped(898, fy+64, 590, 'Step manual membuka Figma, block section, lalu download PDF diganti oleh Figma API Playground: load file, pilih section, export split PDF ZIP otomatis.', F_FOOTER, COL['ink'], 8)

rounded(1580, fy, 2160, 3260, 'white', '#b6bdc6', 16, 1)
d.text((1608, fy+26), 'TEKNOLOGI UTAMA', font=F_FOOTER_B, fill=COL['ink'])
draw_wrapped(1608, fy+64, 500, 'Python, Flask, Figma REST API, MongoDB/GridFS, Groq LLM/Vision, Tesseract OCR, Bootstrap 5, Render.', F_FOOTER, COL['ink'], 8)

png = OUT / 'FUT_Automation_Figma_API_Playground_Clean.png'
svg = OUT / 'FUT_Automation_Figma_API_Playground_Clean.svg'
img.save(png, quality=95)
b64 = base64.b64encode(png.read_bytes()).decode('ascii')
svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><image href="data:image/png;base64,{b64}" width="{W}" height="{H}"/></svg>', encoding='utf-8')
print(png)
print(svg)
