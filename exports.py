"""Standalone local PDF/PNG renderer; invoked with records on stdin."""
import io, json, sys, zipfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from storage import FIELDS

FONT='/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
WIDTH, HEIGHT = 1800, 1272
MARGIN=40
COLS=[140,180,190,250,190,180,150,220,220]
COLS=[v*(WIDTH-2*MARGIN)/sum(COLS) for v in COLS]
font=ImageFont.truetype(FONT,20)

def wrap(text,width):
    lines=[]
    for paragraph in text.split('\n'):
        line=''
        for char in paragraph:
            if line and font.getlength(line+char)>width:
                lines.append(line);line=char
            else:line+=char
        lines.append(line)
    return lines

def pages(rows,cols=COLS):
    page=[];y=155
    for row in rows:
        lines=[wrap(v.replace('\t','    '),w-20) for v,w in zip(row,cols)]
        offset=0;length=max(map(len,lines))
        while offset<length:
            space=int((HEIGHT-70-y-20)//28)
            if space<1:
                yield page;page=[];y=155;continue
            take=min(space,length-offset)
            height=take*28+20
            page.append((y,height,[ls[offset:offset+take] for ls in lines]))
            y+=height;offset+=take
            if offset<length:
                yield page;page=[];y=155
    if page or not rows:yield page

def render(rows,fmt,fields=FIELDS,title='重要信息记录'):
    cols=COLS if len(fields)==9 else [210,240,470,230,350,220]
    cols=[v*(WIDTH-2*MARGIN)/sum(cols) for v in cols]
    out=io.BytesIO()
    if fmt=='pdf':
        pdfmetrics.registerFont(TTFont('Ledger',FONT))
        doc=canvas.Canvas(out,pagesize=(WIDTH/2,HEIGHT/2));doc.setTitle(title)
    else:
        archive=zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED)
    single=None;count=0
    for count,entries in enumerate(pages(rows,cols),1):
        image=Image.new('RGB',(WIDTH,HEIGHT),'white') if fmt=='png' else None
        draw=ImageDraw.Draw(image) if image else None
        def rect(x,y,w,h,fill):
            if draw:draw.rectangle((x,y,x+w,y+h),fill=fill,outline='#e0d6e8',width=1)
            else:
                doc.setFillColor(fill);doc.setStrokeColor('#e0d6e8');doc.rect(x/2,(HEIGHT-y-h)/2,w/2,h/2,fill=1,stroke=1)
        def text(x,y,value,size=20,color='#302b38'):
            if draw:draw.text((x,y),value,font=ImageFont.truetype(FONT,size),fill=color)
            else:
                doc.setFont('Ledger',size/2);doc.setFillColor(color);doc.drawString(x/2,(HEIGHT-y-size)/2,value)
        text(40,30,title,32)
        text(40,82,f'共 {len(rows)} 条记录',18,color='#796784')
        x=MARGIN
        for field,w in zip(fields,cols):
            rect(x,110,w,45,'#e2d4ed');text(x+10,119,field);x+=w
        for idx,(y,h,cells) in enumerate(entries):
            x=MARGIN
            for lines,w in zip(cells,cols):
                rect(x,y,w,h,'#ffffff' if idx%2==0 else '#faf7fc')
                for n,line in enumerate(lines):text(x+10,y+8+n*28,line)
                x+=w
        if not rows:text(50,190,'暂无记录')
        text(40,HEIGHT-45,f'第 {count} 页',18,color='#796784')
        if image:
            buffer=io.BytesIO();image.save(buffer,format='PNG');raw=buffer.getvalue()
            if count==1:single=raw
            archive.writestr(f'重要信息-{count:03}.png',raw)
        else:doc.showPage()
    if fmt=='pdf':doc.save();return out.getvalue()
    archive.close()
    return single if count==1 else out.getvalue()

def render_bundle(tables, fmt):
    """Render several differently-shaped tables into one PDF or PNG archive."""
    out=io.BytesIO()
    if fmt=='pdf':
        pdfmetrics.registerFont(TTFont('Ledger',FONT))
        doc=canvas.Canvas(out,pagesize=(WIDTH/2,HEIGHT/2));doc.setTitle('重要信息记录 · 全部表格')
    else:
        archive=zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED)
    image_index=0
    for title,fields,rows in tables:
        cols=[210,240,470,230,350,220] if len(fields)==6 else COLS
        cols=[v*(WIDTH-2*MARGIN)/sum(cols) for v in cols]
        for page_no,entries in enumerate(pages(rows,cols),1):
            image=Image.new('RGB',(WIDTH,HEIGHT),'white') if fmt=='png' else None
            draw=ImageDraw.Draw(image) if image else None
            def rect(x,y,w,h,fill):
                if draw:draw.rectangle((x,y,x+w,y+h),fill=fill,outline='#e0d6e8',width=1)
                else:
                    doc.setFillColor(fill);doc.setStrokeColor('#e0d6e8');doc.rect(x/2,(HEIGHT-y-h)/2,w/2,h/2,fill=1,stroke=1)
            def text(x,y,value,size=20,color='#302b38'):
                if draw:draw.text((x,y),value,font=ImageFont.truetype(FONT,size),fill=color)
                else:
                    doc.setFont('Ledger',size/2);doc.setFillColor(color);doc.drawString(x/2,(HEIGHT-y-size)/2,value)
            text(40,30,title,32);text(40,82,f'共 {len(rows)} 条记录',18,color='#796784')
            x=MARGIN
            for field,w in zip(fields,cols):
                rect(x,110,w,45,'#e2d4ed');text(x+10,119,field);x+=w
            for idx,(y,h,cells) in enumerate(entries):
                x=MARGIN
                for lines,w in zip(cells,cols):
                    rect(x,y,w,h,'#ffffff' if idx%2==0 else '#faf7fc')
                    for n,line in enumerate(lines):text(x+10,y+8+n*28,line)
                    x+=w
            text(40,HEIGHT-45,f'{title} · 第 {page_no} 页',18,color='#796784')
            if image:
                buffer=io.BytesIO();image.save(buffer,format='PNG');image_index+=1
                archive.writestr(f'{image_index:03}-{title}.png',buffer.getvalue())
            else:doc.showPage()
    if fmt=='pdf':
        doc.save();return out.getvalue()
    archive.close();return out.getvalue()

if __name__=='__main__':
    data=json.load(sys.stdin)
    if data.get('tables'):
        sys.stdout.buffer.write(render_bundle([(item['title'],item['fields'],item['rows']) for item in data['tables']],data['format']))
    else:
        sys.stdout.buffer.write(render(data['rows'],data['format'],data.get('fields',FIELDS),data.get('title','重要信息记录')))
