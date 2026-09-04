from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/documents/phase7_meeting_notes.pdf'
FONT=Path('C:/Windows/Fonts/msyh.ttc')
def main():
 OUT.parent.mkdir(parents=True,exist_ok=True); pdfmetrics.registerFont(TTFont('MicrosoftYaHei',str(FONT)))
 c=canvas.Canvas(str(OUT),pagesize=A4); w,h=A4; c.setTitle('接口评审会议纪要')
 c.setFont('MicrosoftYaHei',18); c.drawString(55,h-65,'接口评审会议纪要')
 c.setFont('MicrosoftYaHei',10); c.drawString(55,h-88,'虚构项目资料  2026-09-05  仅用于 SaaSGuide P7 解析测试')
 y=h-130
 for title,body in [('项目','project-001 星云 CRM 升级项目'),('结论','接口评审未通过，需补充鉴权失败场景和回滚方案。'),('行动','技术负责人于 2026-09-08 前补充材料，再次提交人工评审。'),('边界','本文件没有真实客户、真实会议或生产系统数据。')]:
  c.setFont('MicrosoftYaHei',12); c.drawString(55,y,title); y-=22; c.setFont('MicrosoftYaHei',10); c.drawString(70,y,body); y-=38
 c.setFont('MicrosoftYaHei',9); c.drawRightString(w-55,35,'第 1 页 / 共 1 页'); c.save(); print(OUT)
if __name__=='__main__': main()
