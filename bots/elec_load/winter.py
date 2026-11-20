"""冬季预警日报：负荷、两类纪录、创新高说明及电煤情况。"""
import math
import os

from .renderer import (
    np, plt, mpatches, FancyBboxPatch, LinearSegmentedColormap,
    _fp, _img, _mpl_wrap, BJ_PATH, LM_PATH, JB_PATH,
    PX_W, DPI, TBL_X, TBL_W, COL0, COL1, COL2, RADIUS,
    HDR_H, TITLE_CY, META_Y, META_H, COL_HDR_H, ROW_H,
    WHITE, DARK, TEAL, TEAL_L, CELL_B, CELL_W, CELL_G, BORDER,
)

WINTER_COLOR = '#F5A12B'
HISTORY_COLOR = '#FF0000'
# 参考图取色：深色标签区使用亮青绿粗线，浅色数据区使用灰青细线。
LABEL_BORDER = TEAL_L       # #2B9B97
DATA_BORDER = BORDER       # #437A83
LABEL_BORDER_WIDTH = 1.5
DATA_BORDER_WIDTH = .8
COAL_NOTE = ('中国进口电煤采购价格指数为周度价格（每周五更新，统计周期为更新日前七天）。'
             '燃煤电厂库存量原则上不少于15天耗煤量，秦皇岛港5500大卡下水煤现货交易价格上限1155元/吨，超出上限需重点预警关注。')
MARK_FIELDS = {
    'today_max_company', 'today_max_grid', 'today_peak_cut_company', 'today_peak_cut_grid',
    'prev_max_company', 'prev_max_grid', 'next_max_company', 'next_max_grid',
}


def record_kind(data, field):
    """只采用明确标记，不从当日值等于季内最大值推断创新高。"""
    mark = data.get('record_marks', {}).get(field, {})
    kind = mark.get('kind') if isinstance(mark, dict) else None
    try:
        value = float(data.get(field, '/'))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    return kind if field in MARK_FIELDS and kind in ('winter', 'history') else None


def render_winter_png(data, output_path):
    measure = plt.figure(figsize=(PX_W/DPI, 1), dpi=DPI)
    try:
        note_lines = []
        for segment in str(data.get('note') or '').splitlines():
            if segment.strip():
                note_lines.extend(_mpl_wrap(measure, '　　'+segment.strip(), TBL_W-80, _fp(36,'b')))
        coal = data.get('coal') or {}
        coal_lines = _mpl_wrap(measure, '注：'+str(coal.get('note') or COAL_NOTE), TBL_W, _fp(27,'b'))
    finally:
        plt.close(measure)
    table_y = 855
    table_h = COL_HDR_H+7*ROW_H
    legend_y = table_y+table_h+25
    note_y = legend_y+105
    note_h = 110+60+max(1,len(note_lines))*58
    coal_y = note_y+note_h+35
    coal_header, coal_col_header = 115, 129
    coal_rows = (129, 160, 160)
    coal_h = coal_header+coal_col_header+sum(coal_rows)
    footer_y = coal_y+coal_h+25
    total_h = int(footer_y+len(coal_lines)*47+35)

    fig = plt.figure(figsize=(PX_W/DPI,total_h/DPI),dpi=DPI)
    try:
        ax = fig.add_axes([0,0,1,1]); ax.set_xlim(0,PX_W); ax.set_ylim(total_h,0); ax.axis('off')
        bj = _img(BJ_PATH)
        if bj is not None:
            ax.imshow(bj,extent=[0,PX_W,total_h,0],aspect='auto',zorder=0)
        lm = _img(LM_PATH)
        if lm is not None:
            half=lm[:,lm.shape[1]//2:,:]; h=int(total_h*.5); w=int(half.shape[1]*h/lm.shape[0]); y=(total_h-h)//2
            ax.imshow(half,extent=[0,w,y+h,y],aspect='auto',zorder=1,alpha=.85)
        jb=_img(JB_PATH)
        if jb is not None:
            h=int(HDR_H*.75); w=int(jb.shape[1]*h/jb.shape[0]); y=(HDR_H-h)//2
            ax.imshow(jb,extent=[60,60+w,y+h,y],aspect='auto',zorder=2)
        title='迎峰度冬最大用电负荷情况'
        for dx,dy,color,z in [(8,10,(181/255,209/255,227/255,.67),3),(0,0,'#000000',4)]:
            ax.text(PX_W/2+dx,TITLE_CY+dy,title,ha='center',va='top',fontproperties=_fp(90,'h'),color=color,zorder=z)
        mx,mw=80,PX_W-160
        meta=FancyBboxPatch((mx,META_Y),mw,META_H,boxstyle='round,pad=0,rounding_size=27',facecolor='none',edgecolor='none')
        ax.add_patch(meta)
        cmap=LinearSegmentedColormap.from_list('winter_meta',[(1,1,1,1),(1,1,1,.12),(.059,.365,.345,.35)])
        grad=cmap(np.linspace(0,1,256)).reshape(256,1,4)
        im=ax.imshow(grad,extent=[mx,mx+mw,META_Y+META_H,META_Y],aspect='auto',zorder=2); im.set_clip_path(meta)
        ax.text(mx+60,META_Y+META_H/2,data.get('dept','用电监测分析专班'),va='center',fontproperties=_fp(40),color='black',zorder=4)
        ax.text(mx+mw-60,META_Y+META_H/2,data.get('report_date',''),ha='right',va='center',fontproperties=_fp(40),color='black',zorder=4)

        def frame(y,h,label_width=None):
            clip=FancyBboxPatch((TBL_X,y),TBL_W,h,boxstyle=f'round,pad=0,rounding_size={RADIUS}',facecolor='none',edgecolor='none')
            ax.add_patch(clip)
            # 主表外框沿左右区域分色，说明框及电煤框沿用青绿色圆角外框。
            ax.add_patch(FancyBboxPatch((TBL_X,y),TBL_W,h,boxstyle=f'round,pad=0,rounding_size={RADIUS}',facecolor='none',edgecolor=DATA_BORDER if label_width else LABEL_BORDER,lw=DATA_BORDER_WIDTH if label_width else 1.2,zorder=7))
            if label_width:
                left_outline=FancyBboxPatch((TBL_X,y),TBL_W,h,boxstyle=f'round,pad=0,rounding_size={RADIUS}',facecolor='none',edgecolor=LABEL_BORDER,lw=LABEL_BORDER_WIDTH,zorder=8)
                ax.add_patch(left_outline)
                left_outline.set_clip_path(mpatches.Rectangle((TBL_X-5,y-5),label_width+5,h+10,transform=ax.transData))
            return clip

        def cell(x,y,w,h,text,bg,clip,size=38,color=DARK,mark=None):
            is_label = bg == TEAL
            rect=mpatches.Rectangle((x,y),w,h,facecolor=bg,
                                   edgecolor=LABEL_BORDER if is_label else DATA_BORDER,
                                   lw=LABEL_BORDER_WIDTH if is_label else DATA_BORDER_WIDTH,
                                   zorder=3 if is_label else 2)
            rect.set_clip_path(clip); ax.add_patch(rect)
            value='/' if text is None else str(text)
            fp=_fp(size,'b')
            # 根据真实字宽缩小过长标签，避免“日期+单位”超出单元格。
            t=ax.text(x+w/2,y+h/2,value,ha='center',va='center',fontproperties=fp,color=color,zorder=4,linespacing=1.3)
            renderer=fig.canvas.get_renderer()
            box=t.get_window_extent(renderer)
            factor=min(1,(w-36)/max(1,box.width),(h-24)/max(1,box.height))
            if factor<1:
                fp=_fp(max(20,size*factor),'b'); t.set_fontproperties(fp)
            t.set_clip_path(clip); t.set_clip_on(True)
            if mark:
                box=t.get_window_extent(renderer); star_size=fp.get_size(); color_star=HISTORY_COLOR if mark=='history' else WINTER_COLOR
                # 数字和星号作为一组居中，标记不会挤到单元格边界。
                star_w=star_size*DPI/72
                t.set_x(x+w/2-(star_w+8)/2)
                star=ax.text(x+w/2+box.width/2+4,y+h/2,'★',ha='left',va='center',fontproperties=_fp(star_size,'b'),color=color_star,zorder=5)
                star.set_clip_path(clip); star.set_clip_on(True)

        clip=frame(table_y,table_h,label_width=COL0)
        x0=TBL_X; x1=x0+COL0; x2=x1+COL1
        for x,w,text,bg in [(x0,COL0,'',TEAL),(x1,COL1,'公司经营区',CELL_B),(x2,COL2,'全国',CELL_B)]:
            cell(x,table_y,w,COL_HDR_H,text,bg,clip,size=42)
        date=data.get('date_label','当日'); next_date=data.get('next_date_label','次日')
        rows=[
            (f'{date}最大负荷(亿千瓦)','today_max_company','today_max_grid',CELL_W),
            (f'{date}削峰负荷(万千瓦)','today_peak_cut_company','today_peak_cut_grid',CELL_W),
            ('度冬以来最大负荷(亿千瓦)','winter_max_company','winter_max_grid',CELL_B),
            ('度冬最大削峰负荷(万千瓦)','winter_peak_cut_company','winter_peak_cut_grid',CELL_B),
            ('度冬以来创冬季新高次数','winter_record_high_company','winter_record_high_grid',CELL_W),
            ('前一日最大负荷(亿千瓦)','prev_max_company','prev_max_grid',CELL_G),
            (f'{next_date}预测值(亿千瓦)','next_max_company','next_max_grid',CELL_B),
        ]
        y=table_y+COL_HDR_H
        for label,k1,k2,bg in rows:
            cell(x0,y,COL0,ROW_H,label,TEAL,clip,color=WHITE)
            cell(x1,y,COL1,ROW_H,data.get(k1,'/'),bg,clip,mark=record_kind(data,k1))
            cell(x2,y,COL2,ROW_H,data.get(k2,'/'),bg,clip,mark=record_kind(data,k2))
            y+=ROW_H
        xx=TBL_X+25
        for text,color in [('注：',DARK),('★',WINTER_COLOR),(' 表示创冬季新高，',DARK),('★',HISTORY_COLOR),('表示创历史新高',DARK)]:
            t=ax.text(xx,legend_y,text,va='top',fontproperties=_fp(31,'b'),color=color,zorder=4)
            xx+=t.get_window_extent(fig.canvas.get_renderer()).width

        clip=frame(note_y,note_h)
        cell(TBL_X,note_y,TBL_W,110,'公司经营区及各省市创新高情况',TEAL,clip,size=40,color=WHITE)
        rect=mpatches.Rectangle((TBL_X,note_y+110),TBL_W,note_h-110,facecolor=WHITE,edgecolor='none',zorder=2); rect.set_clip_path(clip); ax.add_patch(rect)
        for i,line in enumerate(note_lines or ['/']):
            t=ax.text(TBL_X+40,note_y+140+i*58,line,va='top',fontproperties=_fp(36,'b'),color=DARK,zorder=4);t.set_clip_path(clip);t.set_clip_on(True)

        clip=frame(coal_y,coal_h)
        cell(TBL_X,coal_y,TBL_W,coal_header,'电煤相关情况',TEAL,clip,size=40,color=WHITE)
        widths=(820,472,TBL_W-820-472);xx=TBL_X; y=coal_y+coal_header
        for w,text,bg in zip(widths,('',coal.get('date_label','/'),'较上一期变化'),(TEAL,CELL_W,CELL_W)):
            cell(xx,y,w,coal_col_header,text,bg,clip,size=39);xx+=w
        coal_data=[
            ('国网(含蒙西)电煤可用天数','available_days','available_days_change'),
            ('中国进口电煤(Q7000K)\n采购价格指数(元/吨)','import_price','import_price_change'),
            ('秦皇岛港5500大卡\n下水煤现货平仓价(元/吨)','port_price','port_price_change'),
        ]
        y+=coal_col_header
        for i,((label,key,change),h) in enumerate(zip(coal_data,coal_rows)):
            cell(TBL_X,y,widths[0],h,label,TEAL,clip,color=WHITE,size=36)
            cell(TBL_X+widths[0],y,widths[1],h,coal.get(key,'/'),CELL_B if i%2==0 else CELL_W,clip,size=40)
            cell(TBL_X+widths[0]+widths[1],y,widths[2],h,coal.get(change,'/'),CELL_B if i%2==0 else CELL_W,clip,size=40)
            y+=h
        for i,line in enumerate(coal_lines):
            ax.text(TBL_X,footer_y+i*47,line,va='top',fontproperties=_fp(27,'b'),color=DARK,zorder=4)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)),exist_ok=True)
        fig.savefig(output_path,dpi=DPI,facecolor='none')
    finally:
        plt.close(fig)
    return output_path


WINTER_EXAMPLE = {
    'season':'winter','report_date':'2026年11月18日','date_label':'11月18日','next_date_label':'11月19日',
    'today_max_company':'10.22','today_max_grid':'12.99','today_peak_cut_company':'/','today_peak_cut_grid':'/',
    'winter_max_company':'10.22','winter_max_grid':'12.99','winter_peak_cut_company':'35.0','winter_peak_cut_grid':'/',
    'winter_record_high_company':'0','winter_record_high_grid':'0',
    'prev_max_company':'10.09','prev_max_grid':'12.80','next_max_company':'10.26','next_max_grid':'12.89',
    'record_marks':{},
    'note':'今年度冬以来，公司经营区最大负荷未创新高;分省看，3个省级电网累计7次创冬季新高，其中甘肃(3次)、西藏(3次)、宁夏（1次），2个省级电网累计5次创历史新高，其中甘肃(3次)、西藏(2次)。',
    'coal':{'date_label':'11月17日','available_days':'32','available_days_change':'0','import_price':'1296','import_price_change':'+17','port_price':'1018','port_price_change':'-6','note':COAL_NOTE},
}
