"""预警日报冬季字段、纪录口径和绘图测试，不调用网络或生成临时图片。"""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from matplotlib.figure import Figure
from bots.elec_load import parser, renderer
from bots.elec_load.winter import WINTER_EXAMPLE, WINTER_COLOR, HISTORY_COLOR, record_kind


class WinterWarningTests(unittest.TestCase):
    def test_equal_maximum_and_forecast_do_not_imply_record(self):
        self.assertEqual(WINTER_EXAMPLE['today_max_company'],WINTER_EXAMPLE['winter_max_company'])
        self.assertIsNone(record_kind(WINTER_EXAMPLE,'today_max_company'))
        # 截图中的次日预测大于季内最大值，也不能自行加星。
        self.assertIsNone(record_kind(WINTER_EXAMPLE,'next_max_company'))

    def test_zero_and_missing_cannot_be_marked(self):
        for value in ('0','/','',None,'nan'):
            data=deepcopy(WINTER_EXAMPLE)
            data['today_max_company']=value
            data['record_marks']={'today_max_company':{'kind':'winter','evidence':'创冬季新高'}}
            self.assertIsNone(record_kind(data,'today_max_company'))
            with self.assertRaises(ValueError):
                parser.validate_record_marks(data,'创冬季新高')

    def test_records_need_positive_exact_source_evidence(self):
        data=deepcopy(WINTER_EXAMPLE)
        evidence='公司经营区当日最大负荷10.22亿千瓦创冬季新高'
        data['record_marks']={'today_max_company':{'kind':'winter','evidence':evidence}}
        self.assertIs(parser.validate_record_marks(data,evidence),data)
        self.assertEqual(record_kind(data,'today_max_company'),'winter')
        with self.assertRaises(ValueError): parser.validate_record_marks(data,'其他原文')
        data['record_marks']['today_max_company']['evidence']='公司经营区未创冬季新高'
        with self.assertRaises(ValueError): parser.validate_record_marks(data,'公司经营区未创冬季新高')

    def test_history_takes_priority(self):
        data=deepcopy(WINTER_EXAMPLE)
        text='公司经营区当日创冬季和历史新高'
        data['record_marks']={'today_max_company':{'kind':'winter','evidence':text}}
        with self.assertRaises(ValueError): parser.validate_record_marks(data,text)
        data['record_marks']['today_max_company']['kind']='history'
        parser.validate_record_marks(data,text)
        self.assertEqual(record_kind(data,'today_max_company'),'history')

    def test_default_parser_and_signed_coal_changes(self):
        reply=SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(WINTER_EXAMPLE,ensure_ascii=False)))])
        with patch.object(parser,'OpenAI') as sdk:
            sdk.return_value.chat.completions.create.return_value=reply
            result=parser.parse_elec_load('测试文本')
            self.assertEqual(result['season'],'winter')
            self.assertEqual(result['coal']['import_price_change'],'+17')
            self.assertEqual(result['coal']['port_price_change'],'-6')
            self.assertEqual(sdk.return_value.chat.completions.create.call_args.kwargs['messages'][0]['content'],parser.SYSTEM_PROMPT)
            parser.parse_elec_load('夏季测试',season='summer')
            self.assertEqual(sdk.return_value.chat.completions.create.call_args.kwargs['messages'][0]['content'],parser.SUMMER_SYSTEM_PROMPT)

    def test_winter_drawing_and_both_star_colors(self):
        data=deepcopy(WINTER_EXAMPLE)
        data['record_marks']={'today_max_company':{'kind':'winter'},'today_max_grid':{'kind':'history'}}
        captured=[]
        def capture(figure,*args,**kwargs):
            captured.extend((t.get_text(),t.get_color()) for ax in figure.axes for t in ax.texts)
        # 拦截保存检查实际绘制对象，测试不产生图片文件。
        with patch.object(Figure,'savefig',capture):
            renderer.render_elec_load_png(data,str(Path(__file__).resolve().parents[1]/'output'/'not_written.png'))
        stars=[color for text,color in captured if text=='★']
        self.assertEqual(stars.count(WINTER_COLOR),2)
        self.assertEqual(stars.count(HISTORY_COLOR),2)
        text=[t for t,c in captured]
        for expected in ('迎峰度冬最大用电负荷情况','电煤相关情况','11月17日','32','1296','+17','1018','-6'):
            self.assertIn(expected,text)
        self.assertNotIn('度夏以来最大负荷(亿千瓦)',text)

    def test_summer_renderer_remains_available(self):
        with patch.object(renderer,'render_summer_elec_load_png',return_value='summer.png') as summer:
            self.assertEqual(renderer.render_elec_load_png({'season':'summer'},'summer.png'),'summer.png')
            summer.assert_called_once()


if __name__=='__main__': unittest.main()
