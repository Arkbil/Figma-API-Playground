from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import textwrap, base64, math

src = Path(r'D:\WhatsApp Image 2026-07-04 at 12.33.19.jpeg')
out_dir = Path(r'D:\Magang Telkomsel\FUT\fut-ai-automation-main\fut-ai-automation-main\figma-api-playground\docs')
out_dir.mkdir(parents=True, exist_ok=True)
img = Image.open(src).convert('RGB')
d = ImageDraw.Draw(img)
W,H = img.size

def font(size, bold=False):
    paths = [r'C:\Windows\Fonts\arialbd.ttf' if bold else r'C:\Windows\Fonts\arial.ttf', r'C:\Windows\Fonts\segoeuib.ttf' if bold else r'C:\Windows\Fonts\segoeui.ttf']
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

F_TITLE = font(14, True)
F_BOX_T = font(11, True)
F_BODY = font(9)
F_SMALL = font(8)
F_NUM = font(15, True)

INK = '#111111'
MUTED = '#253243'
GREEN_BG = '#eef9ee'
GREEN_BORDER = '#3d9b55'
BOX_BORDER = '#4d4d4d'
YELLOW_BG = '#fff9df'
WHITE = '#ffffff'
ARROW = '#111111'

# Redraw only Section 2, preserving the source diagram everywhere else.
sec_x, sec_y, sec_w, sec_h = 18, 486, 820, 162
# cover original section 2 with same style panel
d.rounded_rectangle((sec_x, sec_y, sec_x+sec_w, sec_y+sec_h), radius=7, fill=GREEN_BG, outline=GREEN_BORDER, width=1)
d.rectangle((sec_x, sec_y, sec_x+27, sec_y+27), fill=GREEN_BORDER)
d.text((sec_x+9, sec_y+4), '2', font=F_NUM, fill='white')
d.text((sec_x+37, sec_y+10), 'BUAT PROJECT & GENERATE TEST CASE', font=F_TITLE, fill='#23803b')
d.text((sec_x+37, sec_y+26), '(Via Figma API Playground)', font=F_SMALL, fill='#23803b')

def text_size(text, f):
    b = d.textbbox((0,0), text, font=f)
    return b[2]-b[0], b[3]-b[1]

def wrap_px(text, f, max_w):
    lines = []
    for para in text.split('\n'):
        words = para.split()
        if not words:
            lines.append('')
            continue
        cur = ''
        for word in words:
            cand = word if not cur else cur + ' ' + word
            if text_size(cand, f)[0] <= max_w:
                cur = cand
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines

def draw_wrapped(x, y, w, text, f, fill=INK, gap=2, max_lines=5):
    lines = wrap_px(text, f, w)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip('.') + '...'
    yy = y
    for line in lines:
        d.text((x, yy), line, font=f, fill=fill)
        yy += text_size(line or 'A', f)[1] + gap

def box(x, y, w, h, title, body, fill=WHITE):
    d.rounded_rectangle((x,y,x+w,y+h), radius=4, fill=fill, outline=BOX_BORDER, width=1)
    d.text((x+10,y+11), title, font=F_BOX_T, fill=INK)
    draw_wrapped(x+10, y+30, w-20, body, F_BODY, INK, gap=2, max_lines=4)

def arrow(x1,y1,x2,y2):
    d.line((x1,y1,x2,y2), fill=ARROW, width=1)
    ang = math.atan2(y2-y1, x2-x1)
    l = 7
    pts = [(x2,y2),(x2-l*math.cos(ang-0.45),y2-l*math.sin(ang-0.45)),(x2-l*math.cos(ang+0.45),y2-l*math.sin(ang+0.45))]
    d.polygon(pts, fill=ARROW)

# Source-like box placement: keep same one-row grammar as original.
y = 535
h = 84
boxes = [
    (48, 150, 'Buat Project Baru', 'Isi metadata project: nama, channel, environment, PIC, target, dan coverage.'),
    (210, 145, 'Load Figma API', 'Pilih Saved Figma atau input token + file key. Ambil pages, sections, frames.'),
    (365, 150, 'Pilih Section Flow', 'Centang section yang menjadi flow. Export split PDF: 1 section = 1 PDF.'),
    (528, 160, 'Generate Test Case (AI)', 'AI membaca split PDF + knowledge base untuk membuat section, scenario, steps, expected result.'),
    (700, 118, 'Test Case Siap', 'Siap untuk testing dan auto matching.')
]
for x,w,title,body in boxes:
    fill = YELLOW_BG if title == 'Pilih Section Flow' else WHITE
    box(x, y, w, h, title, body, fill)
for i in range(len(boxes)-1):
    x,w,_,_ = boxes[i]
    nx,nw,_,_ = boxes[i+1]
    arrow(x+w, y+h//2, nx, y+h//2)

# small fallback note, still inside section 2 and not disturbing source layout
note_x, note_y, note_w, note_h = 365, 625, 300, 18
d.rounded_rectangle((note_x,note_y,note_x+note_w,note_y+note_h), radius=4, fill='#fff7e6', outline='#d8a52d', width=1)
d.text((note_x+8,note_y+4), 'Fallback: jika API/rate limit gagal, upload Figma PDF manual tetap bisa dipakai.', font=F_SMALL, fill='#5b4210')

# Add one minimal component note in right sidebar without redrawing the whole sidebar.
# It replaces only part of the Frontend/Backend stack area that is visually close to the integration point.
comp_x, comp_y, comp_w, comp_h = 866, 495, 138, 76
d.rounded_rectangle((comp_x, comp_y, comp_x+comp_w, comp_y+comp_h), radius=5, fill='#eef9ee', outline='#9aa3ad', width=1)
d.text((comp_x+12, comp_y+9), 'FIGMA API', font=F_BOX_T, fill=INK)
draw_wrapped(comp_x+12, comp_y+27, comp_w-24, 'REST API\nSaved token lokal\nSplit PDF ZIP', F_SMALL, INK, gap=2, max_lines=4)

png = out_dir / 'FUT_Automation_Figma_API_Playground_SourceStyle.png'
svg = out_dir / 'FUT_Automation_Figma_API_Playground_SourceStyle.svg'
img.save(png, quality=95)
b64 = base64.b64encode(png.read_bytes()).decode('ascii')
svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><image href="data:image/png;base64,{b64}" width="{W}" height="{H}"/></svg>', encoding='utf-8')
print(png)
print(svg)
