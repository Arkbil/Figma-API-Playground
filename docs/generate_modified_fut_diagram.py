from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import textwrap, base64, math
OUT = Path(r'D:\Magang Telkomsel\FUT\fut-ai-automation-main\fut-ai-automation-main\figma-api-playground\docs')
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1800, 2600
img = Image.new('RGB', (W, H), '#fbfbf7')
d = ImageDraw.Draw(img)
def font(size, bold=False):
    candidates = [r'C:\Windows\Fonts\arialbd.ttf' if bold else r'C:\Windows\Fonts\arial.ttf', r'C:\Windows\Fonts\segoeuib.ttf' if bold else r'C:\Windows\Fonts\segoeui.ttf']
    for p in candidates:
        if Path(p).exists(): return ImageFont.truetype(p, size)
    return ImageFont.load_default()
F_TITLE=font(42,True); F_SUB=font(22); F_H=font(25,True); F_BOX_H=font(18,True); F_SMALL=font(13); F_TINY=font(12); F_NUM=font(24,True)
COL={'navy':'#07345a','line':'#1d2a35','muted':'#53616f','blue':'#e9f4ff','blue_s':'#1b67a7','green':'#e9f8ed','green_s':'#2f8f4e','yellow':'#fff8df','yellow_s':'#d4a21f','purple':'#f4edff','purple_s':'#7d48a8','orange':'#fff1e1','orange_s':'#e47c22','red':'#ffe8e8','red_s':'#d64646','gray':'#f5f6f7','gray_s':'#aab3bd','black':'#1e2329'}
def rounded(xy,fill,outline,r=16,width=2): d.rounded_rectangle(xy,r,fill=fill,outline=outline,width=width)
def wrap_lines(text,max_chars):
    out=[]
    for part in text.split('\n'): out.extend(textwrap.wrap(part,width=max_chars) or [''])
    return out
def text_center(xy,text,fnt,fill=COL['black'],spacing=4):
    x1,y1,x2,y2=xy; lines=wrap_lines(text,max(8,int((x2-x1)/9))); dims=[d.textbbox((0,0),l,font=fnt) for l in lines]
    hs=[b[3]-b[1] for b in dims]; ws=[b[2]-b[0] for b in dims]; total=sum(hs)+spacing*(len(lines)-1); y=y1+(y2-y1-total)/2
    for line,w,h in zip(lines,ws,hs): d.text((x1+(x2-x1-w)/2,y),line,font=fnt,fill=fill); y+=h+spacing
def text_left(x,y,text,fnt,fill=COL['black'],width=25,lh=1.25):
    yy=y
    for line in wrap_lines(text,width):
        d.text((x,yy),line,font=fnt,fill=fill); bb=d.textbbox((0,0),line,font=fnt); yy+=int((bb[3]-bb[1])*lh)+4
    return yy
def arrow(x1,y1,x2,y2,fill=COL['line'],width=3):
    d.line((x1,y1,x2,y2),fill=fill,width=width); ang=math.atan2(y2-y1,x2-x1); l=14
    d.polygon([(x2,y2),(x2-l*math.cos(ang-0.45),y2-l*math.sin(ang-0.45)),(x2-l*math.cos(ang+0.45),y2-l*math.sin(ang+0.45))],fill=fill)
def box(x,y,w,h,title,body,fill,stroke,icon=None):
    rounded((x,y,x+w,y+h),fill,stroke,10,2); tx=x+18
    if icon: d.text((tx,y+16),icon,font=font(24,True),fill=stroke); tx+=42
    d.text((tx,y+18),title,font=F_BOX_H,fill=COL['black']); text_left(x+18,y+50,body,F_SMALL,COL['black'],width=max(16,int((w-36)/7.1)),lh=1.2)
def section(y,num,title,fill,stroke,height):
    x=30; w=1440; rounded((x,y,x+w,y+height),fill,stroke,10,2); d.rectangle((x,y,x+42,y+42),fill=stroke); text_center((x,y,x+42,y+42),str(num),F_NUM,'white'); d.text((x+62,y+16),title,font=F_H,fill=stroke)
# Header
rounded((18,20,W-18,130),COL['navy'],COL['navy'],24,1); text_center((18,34,W-18,78),'FLOWCHART FUT AI AUTOMATION',F_TITLE,'white'); text_center((18,78,W-18,116),'With Figma API Playground for Automated Flow PDF Generation',F_SUB,'white')
# Login
rounded((90,205,220,275),'#e9f8dc','#3a8f46',30,2); text_center((90,210,220,270),'START',F_BOX_H); box(370,175,250,125,'1. LOGIN','User memasukkan\nusername & password','#e8f4ff','#4681b4','U')
cx,cy=850,238; d.polygon([(cx,cy-70),(cx+90,cy),(cx,cy+70),(cx-90,cy)],fill='#fff4cf',outline='#b99d35'); text_center((cx-62,cy-42,cx+62,cy+42),'Validasi\nLogin',F_SMALL)
box(1160,175,270,125,'Dashboard','Daftar project, knowledge,\ndan akses Figma Playground','#e8f8eb','#4f9b58','▦'); box(760,350,240,115,'Login Gagal','Tampilkan pesan error\ndan kembali ke login','#ffe5e5','#d94b4b')
arrow(220,240,370,240); arrow(620,240,760,240); arrow(940,240,1160,240); text_center((980,200,1050,230),'YA',F_BOX_H,'#168a45'); arrow(850,308,850,350); text_center((865,314,940,345),'TIDAK',F_BOX_H,'#c73c3c'); arrow(1295,300,1295,520); d.line((1295,520,580,520),fill=COL['line'],width=3); arrow(580,520,580,575)
# sections
section(575,1,'KELOLA KNOWLEDGE BASE (Historical FUT)',COL['blue'],COL['blue_s'],235)
box(65,660,250,120,'Upload Historical FUT','Upload PDF/DOCX FUT lama\nsebagai referensi AI','white','#7d8792','↥'); box(425,660,285,120,'Parsing Dokumen FUT','Ekstraksi section, scenario,\nsteps, expected result,\nstatus, note, suggestion','white','#7d8792','□'); box(785,660,300,120,'Simpan Knowledge Base','Data disimpan ke MongoDB\nCollection: knowledge_docs\nFile di GridFS','white','#7d8792','DB'); box(1210,660,225,120,'Knowledge Siap','Dipakai AI untuk\ngenerate & matching\ntest case','#fffefa','#7d8792'); arrow(315,720,425,720); arrow(710,720,785,720); arrow(1085,720,1210,720)
section(840,2,'BUAT PROJECT & AMBIL FLOW DARI FIGMA API PLAYGROUND',COL['green'],COL['green_s'],335)
box(65,940,260,130,'Buat Project Baru','Isi nama project, channel,\nenvironment, PIC, target,\ncoverage, dan scope FUT','white','#7d8792','▣'); box(385,940,275,130,'Figma API Playground','Input token + file key\natau Load Saved lokal\n(token tidak ikut Git)','#f0fff4','#2f8f4e','API'); box(720,940,285,130,'Load Struktur Figma','Figma API mengambil pages,\nsections, frames, metadata\n(load data tree)','white','#7d8792','↧'); box(1065,940,250,130,'Pilih Section Flow','User centang section yang\nmenjadi flow FUT dan\nurutan flow','white','#7d8792','☑'); box(1355,940,90,130,'ZIP PDF','Siap','#fffefa','#7d8792'); box(720,1090,285,65,'Fallback Manual','Jika API/rate limit gagal, user masih bisa upload Figma PDF manual','#fff7e6','#d4a21f'); arrow(325,1005,385,1005); arrow(660,1005,720,1005); arrow(1005,1005,1065,1005); arrow(1315,1005,1355,1005); d.line((862,1070,862,1090),fill='#d4a21f',width=2)
section(1205,3,'GENERATE TEST CASE AI (Dari Split Section PDF)',COL['yellow'],COL['yellow_s'],210)
box(65,1290,270,105,'Import Flow PDF','ZIP dari Playground\nberisi 1 section = 1 PDF','white','#7d8792','PDF'); box(430,1290,310,105,'Generate Test Case (AI)','Groq/LLM membaca visual PDF\n+ knowledge base untuk membuat\nsection, scenario, steps, expected','white','#7d8792','AI'); box(845,1290,280,105,'Review & Edit Test Case','User validasi dan edit\ntest case sebelum testing','white','#7d8792','☑'); box(1230,1290,210,105,'Test Case Siap','Siap untuk testing\ndan auto matching','#fffefa','#7d8792'); arrow(335,1342,430,1342); arrow(740,1342,845,1342); arrow(1125,1342,1230,1342)
section(1445,4,'UPLOAD SCREENSHOT HASIL TESTING',COL['yellow'],COL['yellow_s'],205)
box(65,1530,280,105,'Upload Screenshot','Upload gambar hasil testing\n(PNG/JPG/WebP)','white','#7d8792','▧'); box(520,1530,310,105,'Simpan Capture','Gambar dan metadata\ndisimpan di MongoDB GridFS\ncollection captures','white','#7d8792','DB'); box(1020,1530,250,105,'Screenshot Siap','Siap dianalisis oleh AI,\nOCR, dan matching','#fffefa','#7d8792'); arrow(345,1582,520,1582); arrow(830,1582,1020,1582)
section(1680,5,'ANALISIS AI: OCR & AUTO MATCHING',COL['purple'],COL['purple_s'],320)
box(65,1770,240,110,'OCR','Ekstraksi teks dari\nscreenshot testing','white','#7d8792','OCR'); box(375,1770,310,110,'Screen Recognition','AI mengenali screen, state,\nelement, popup, success/error,\ndan konteks','white','#7d8792','◉'); box(755,1770,300,110,'Auto Matching','Cocokkan screenshot\ndengan test case dari flow PDF,\nexpected result, dan konten','white','#7d8792','◎'); box(1120,1770,300,110,'Confidence Score','Skor confidence 0-1\nuntuk setiap hasil match','white','#7d8792','▥'); box(410,1930,245,95,'Matched','Screenshot ditempatkan\nke test case paling sesuai','#e8f8eb','#3d9b58','✓'); box(1040,1930,300,95,'Unassigned Capture','Jika confidence rendah,\nmasuk review manual','#ffe8e8','#d64646','!'); arrow(305,1825,375,1825); arrow(685,1825,755,1825); arrow(1055,1825,1120,1825); arrow(920,1880,535,1930,'#2f8f4e',3); text_center((520,1885,760,1920),'Confidence >= threshold',F_SMALL,'#168a45'); arrow(1270,1880,1190,1930,'#d64646',3); text_center((1110,1885,1405,1920),'Confidence < threshold',F_SMALL,'#c73c3c')
section(2030,6,'REVIEW HASIL & UPDATE STATUS',COL['blue'],COL['blue_s'],205)
box(65,2115,300,105,'Review Matching','Cek screenshot, actual result,\nexpected result, dan confidence','white','#7d8792','≡'); box(560,2115,315,105,'Update Status & Note','NOT_TESTED, PASS, PASS_WITH_NOTE,\nPASS_WITH_SUGGESTION, FAIL, BLOCKED','white','#7d8792','✎'); box(1070,2115,270,105,'Simpan Hasil','Perubahan disimpan\nke MongoDB','white','#7d8792','DB'); arrow(365,2168,560,2168); arrow(875,2168,1070,2168)
section(2265,7,'EXPORT FUT',COL['orange'],COL['orange_s'],180)
box(65,2338,275,90,'Export PDF','Generate dokumen FUT\ndalam format PDF','white','#7d8792','PDF'); box(520,2338,290,90,'Export DOCX','Generate dokumen FUT\ndalam format Word\n(bisa diedit)','white','#7d8792','DOC'); box(990,2338,260,90,'Dokumen FUT Siap','Dibagikan ke stakeholder\natau dilampirkan ke report','#fffefa','#7d8792'); rounded((1360,2345,1460,2418),'#e9f8dc','#3a8f46',28,2); text_center((1360,2345,1460,2418),'END',F_BOX_H); arrow(340,2385,520,2385); arrow(810,2385,990,2385); arrow(1250,2385,1360,2385)
# sidebar
sx,sy,sw,sh=1515,575,250,1670; rounded((sx,sy,sx+sw,sy+sh),'#fbfbfb','#9aa3ad',14,2); text_center((sx+10,sy+20,sx+sw-10,sy+65),'KOMPONEN SISTEM',F_BOX_H)
comp=[('FRONTEND','HTML, CSS, JS\nBootstrap 5\nResponsive UI','#e8f4ff','WEB'),('FIGMA API PLAYGROUND','Figma REST API\nSaved token lokal\nSplit section PDF ZIP','#e9f8ed','FIG'),('BACKEND','Flask/Python\nREST Routes\nBackground Worker','#fff8df','PY'),('AI SERVICES','LLM Text + Vision\nGroq API\nOCR helper','#f4edff','AI'),('DATABASE','MongoDB Atlas\nprojects, test_cases\ncaptures, knowledge_docs\nGridFS storage','#e9f8ed','DB'),('OCR ENGINE','Tesseract OCR\nVision fallback','#f5f6f7','OCR'),('DEPLOYMENT','Render Web Service\nGunicorn\nMongoDB Atlas','#e8f4ff','CLD')]
y=665
for title,body,fill,ic in comp:
    box(sx+25,y,sw-50,175,title,body,fill,'#9aa3ad',ic); y+=205
# bottom
rounded((30,2480,870,2575),'white','#b6bdc6',10,1); d.text((55,2497),'KETERANGAN FLOW',font=font(17,True),fill=COL['black']); notes=['1 Historical FUT menjadi knowledge base AI','2 Figma API Playground mengganti export Figma PDF manual','3 Satu Figma section diexport menjadi satu PDF flow','4 PDF flow dipakai AI untuk generate test case','5 Screenshot hasil testing dicocokkan otomatis','6 Hasil akhir diexport PDF/DOCX']; yy=2525
for n in notes: d.text((55,yy),n,font=F_TINY,fill=COL['black']); yy+=20
rounded((910,2480,1455,2575),'white','#b6bdc6',10,1); d.text((935,2497),'PERUBAHAN UTAMA',font=font(17,True),fill=COL['black']); text_left(935,2525,'Manual block section + download PDF di Figma diganti oleh Load Figma API, pilih section, lalu export split PDF ZIP otomatis.',F_TINY,COL['black'],width=72,lh=1.15)
rounded((1495,2480,1765,2575),'white','#b6bdc6',10,1); d.text((1518,2497),'TEKNOLOGI UTAMA',font=font(17,True),fill=COL['black']); text_left(1518,2525,'Python, Flask, Figma REST API, MongoDB/GridFS, Groq LLM/Vision, Tesseract OCR',F_TINY,COL['black'],width=34,lh=1.15)
png=OUT/'FUT_Automation_Figma_API_Playground_Modified.png'; img.save(png,quality=95)
b64=base64.b64encode(png.read_bytes()).decode('ascii'); svg=OUT/'FUT_Automation_Figma_API_Playground_Modified.svg'; svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><image href="data:image/png;base64,{b64}" width="{W}" height="{H}"/></svg>',encoding='utf-8')
print(png); print(svg)


