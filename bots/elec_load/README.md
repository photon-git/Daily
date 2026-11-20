# 负荷预警日报

当前默认冬季版，飞书入口仍为 `/webhook/elec_load`，无需更换调用方式。解析器提取度冬负荷、削峰、冬季创新高次数、次日预测、创新高说明及电煤数据。

## 冬季数据与纪录标记

季节累计字段使用 `winter_max_company/grid`、`winter_peak_cut_company/grid`、`winter_record_high_company/grid`。公司及全国整体的创新高次数不能用各省合计次数代替。

`coal` 包含 `date_label`、`available_days`、`available_days_change`、`import_price`、`import_price_change`、`port_price`、`port_price_change`、`note`。变化值保留正负号和零，电煤统计日期单独读取。未提供的数字显示 `/`，不填示例值。

`record_marks` 明确指定单元格纪录，例如：

```json
{"today_max_company":{"kind":"winter","evidence":"公司经营区当日最大负荷10.30亿千瓦创冬季新高"}}
```

`winter` 为橙星，`history` 为红星；同时创冬季、历史新高时使用红星。只采用有原文依据且与日期、指标和范围相符的标记，不从当日值等于季内最大值、零值或省级纪录推断整体纪录。原图中的当日值与季内最大值相等、次日预测高于季内最大值，但没有明确整体创新高标记，测试图均不自动加星。省级纪录原文展示在单独的说明框。

## 夏季保留

完整的原夏季提示词保留在 `parser.SUMMER_SYSTEM_PROMPT`，原渲染实现保留为 `renderer.render_summer_elec_load_png`。需要夏季模式时调用 `parse_elec_load(text, season='summer')`，结果自带 `season='summer'`，`render_elec_load_png` 会使用原度夏实现及原字段。缺省为冬季，不将夏季累计值回填冬季表格。

## 本地测试

```powershell
python -X utf8 -m bots.elec_load.renderer --output "D:\elec\Daily\output\预警日报_冬季版_2026-11-18.png"
python -X utf8 -B -m unittest discover -s tests -p test_elec_load.py -v
```

示例数据保存在 `winter.WINTER_EXAMPLE`，来自所提供的11月18日截图。离线绘图不调用 API。不传 `--output` 时，测试图写入工作区 `_temp/elec_load_winter/`，使用后应清理。测试代码本身不保存图片。底部默认说明沿用提供的模板文字；口径调整时应同步更新 `winter.COAL_NOTE`，不是实时查询得到的规则。
