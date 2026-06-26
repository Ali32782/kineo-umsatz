from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session
import os

from database import UmsatzData, MonthlyInput, MAStammdaten
from calc import compute_zeg, compute_soll_tage, zeg_color, MONTH_NAMES_DE

TEAL="006B6B"; WHITE="FFFFFF"; GRAY="F5F5F5"; DARK="1A1A1A"
EXPORTS_DIR=os.environ.get("EXPORTS_DIR",os.path.join(os.path.dirname(__file__),"../exports"))

def bdr():
    s=Side(style='thin',color='CCCCCC'); return Border(left=s,right=s,top=s,bottom=s)
def fc(c,bold=False,bg=WHITE,fg=DARK,align='center',fmt=None,sz=9,wrap=False):
    c.font=Font(name='Arial',bold=bold,color=fg,size=sz)
    c.fill=PatternFill('solid',start_color=bg)
    c.alignment=Alignment(horizontal=align,vertical='center',wrap_text=wrap)
    c.border=bdr()
    if fmt: c.number_format=fmt
def zeg_bg(v):
    if v is None: return GRAY
    if v>=1.0: return "E8F8E8"
    if v>=0.85: return "FFF8E0"
    return "FFE8E8"

def generate_excel(year:int, db:Session)->str:
    mas=db.query(MAStammdaten).filter(MAStammdaten.is_active==True).all()
    umsatz_all={(r.ma_name,r.month):r.umsatz for r in db.query(UmsatzData).filter(UmsatzData.year==year).all()}
    inputs_all={(r.ma_name,r.month):r for r in db.query(MonthlyInput).filter(MonthlyInput.year==year).all()}
    wb=Workbook(); wb.remove(wb.active)

    # ── Übersicht ────────────────────────────────────────────────────────
    ws=wb.create_sheet("Übersicht")
    total_cols=2+12*2
    ws.merge_cells(f'A1:{get_column_letter(total_cols)}1')
    c=ws['A1']; c.value=f'KINEO AG  |  Umsatzanalyse {year}'
    c.font=Font(name='Arial',bold=True,color=WHITE,size=13)
    c.fill=PatternFill('solid',start_color=TEAL)
    c.alignment=Alignment(horizontal='center',vertical='center')
    ws.row_dimensions[1].height=28

    # Row 2: headers
    ws.row_dimensions[2].height=18
    for col,txt in [(1,'Mitarbeiter/in'),(2,'BG%')]:
        c=ws.cell(row=2,column=col,value=txt)
        fc(c,bold=True,bg=TEAL,fg=WHITE,align='left' if col==1 else 'center')
    for mi,mn in enumerate(range(1,13)):
        sc=3+mi*2
        ws.merge_cells(start_row=2,start_column=sc,end_row=2,end_column=sc+1)
        c=ws.cell(row=2,column=sc,value=MONTH_NAMES_DE[mn][:3])
        c.font=Font(name='Arial',bold=True,color=WHITE,size=9)
        c.fill=PatternFill('solid',start_color=TEAL)
        c.alignment=Alignment(horizontal='center',vertical='center')

    # Row 3: sub-headers
    ws.row_dimensions[3].height=16
    fc(ws.cell(row=3,column=1),bold=True,bg=TEAL,fg=WHITE)
    fc(ws.cell(row=3,column=2),bold=True,bg=TEAL,fg=WHITE)
    for mi in range(12):
        for d,txt in enumerate(['Umsatz','ZEG-B']):
            fc(ws.cell(row=3,column=3+mi*2+d,value=txt),bold=True,bg=TEAL,fg=WHITE,sz=8)

    row=4
    for i,ma in enumerate(mas):
        ws.row_dimensions[row].height=17
        bg=WHITE if i%2==0 else GRAY
        fc(ws.cell(row=row,column=1,value=ma.display_name),bold=True,bg=bg,align='left')
        fc(ws.cell(row=row,column=2,value=ma.bg_pct),bg=bg,fmt='0%')
        for mi,mn in enumerate(range(1,13)):
            sc=3+mi*2
            umsatz=umsatz_all.get((ma.name,mn),0)
            inp=inputs_all.get((ma.name,mn))
            soll=compute_soll_tage(ma.name,year,mn)
            if soll==0 and umsatz==0:
                for d in range(2): fc(ws.cell(row=row,column=sc+d),bg=bg,fg='CCCCCC')
                continue
            zeg=compute_zeg(ma.name,year,mn,umsatz,
                ferien_t=inp.ferien_t if inp else 0,kurs_h=inp.kurs_h if inp else 0,
                workshop_h=inp.workshop_h if inp else 0,marketing_h=inp.marketing_h if inp else 0,
                laufanalyse_h=inp.laufanalyse_h if inp else 0,krank_t=inp.krank_t if inp else 0)
            fc(ws.cell(row=row,column=sc,value=umsatz),bg=bg,fmt="#'##0",align='right')
            zb=zeg['zeg_b']
            fc(ws.cell(row=row,column=sc+1,value=zb),bold=bool(zb),bg=zeg_bg(zb),fmt='0.0%' if zb else None)
        row+=1

    ws.column_dimensions['A'].width=16; ws.column_dimensions['B'].width=6
    for mi in range(12):
        ws.column_dimensions[get_column_letter(3+mi*2)].width=10
        ws.column_dimensions[get_column_letter(4+mi*2)].width=8
    ws.freeze_panes='C4'

    # ── Monthly sheets ───────────────────────────────────────────────────
    for mn in range(1,13):
        ws_m=wb.create_sheet(f"{MONTH_NAMES_DE[mn][:3]} {year}")
        ws_m.merge_cells('A1:R1')
        c=ws_m['A1']; c.value=f'KINEO AG  |  {MONTH_NAMES_DE[mn]} {year}'
        c.font=Font(name='Arial',bold=True,color=WHITE,size=11)
        c.fill=PatternFill('solid',start_color=TEAL)
        c.alignment=Alignment(horizontal='center',vertical='center')
        ws_m.row_dimensions[1].height=24

        hdrs=['Name','BG%','Soll','Ferien','Kurse(h)','Workshop(h)','Mkt(h)','Lauf(h)',
              'Mgmt(T)','Leit(T)','Krank(T)','Prod-A','Prod-B','Prod-C','Umsatz','ZEG-A','ZEG-B','ZEG-C']
        ws_m.row_dimensions[2].height=28
        for col,h in enumerate(hdrs,1):
            fc(ws_m.cell(row=2,column=col,value=h),bold=True,bg=TEAL,fg=WHITE,sz=8,wrap=True)

        for i,ma in enumerate(mas):
            r=i+3; ws_m.row_dimensions[r].height=17
            bg=WHITE if i%2==0 else GRAY
            umsatz=umsatz_all.get((ma.name,mn),0)
            inp=inputs_all.get((ma.name,mn))
            soll=compute_soll_tage(ma.name,year,mn)
            zeg=compute_zeg(ma.name,year,mn,umsatz,
                ferien_t=inp.ferien_t if inp else 0,kurs_h=inp.kurs_h if inp else 0,
                workshop_h=inp.workshop_h if inp else 0,marketing_h=inp.marketing_h if inp else 0,
                laufanalyse_h=inp.laufanalyse_h if inp else 0,krank_t=inp.krank_t if inp else 0)
            vals=[ma.display_name,ma.bg_pct,soll,
                inp.ferien_t if inp else None,inp.kurs_h if inp else None,
                inp.workshop_h if inp else None,inp.marketing_h if inp else None,
                inp.laufanalyse_h if inp else None,
                zeg['mgmt_t'] or None,zeg['leit_t'] or None,inp.krank_t if inp else None,
                zeg['prod_a'],zeg['prod_b'],zeg['prod_c'],
                umsatz,zeg['zeg_a'],zeg['zeg_b'],zeg['zeg_c']]
            fmts=['','0%','0.0','0.0','0.0','0.0','0.0','0.0','0.00','0.00','0.0',
                  '0.0','0.0','0.0',"#'##0",'0.0%','0.0%','0.0%']
            for col,(val,fmt) in enumerate(zip(vals,fmts),1):
                cbg=bg
                if col in (16,17,18) and isinstance(val,float): cbg=zeg_bg(val)
                fc(ws_m.cell(row=r,column=col,value=val),bold=(col==1),bg=cbg,
                   align='left' if col==1 else 'center',fmt=fmt if val else None)

        for ci,w in enumerate([16,6,7,7,7,8,7,7,7,7,7,7,7,7,11,8,8,8],1):
            ws_m.column_dimensions[get_column_letter(ci)].width=w
        ws_m.freeze_panes='A3'

    os.makedirs(EXPORTS_DIR,exist_ok=True)
    path=os.path.join(EXPORTS_DIR,f"Kineo_Umsatzanalyse_{year}.xlsx")
    wb.save(path); return path
