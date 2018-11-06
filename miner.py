import sys
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfdevice import PDFDevice
from pdfminer.layout import LAParams
from pdfminer.converter import PDFPageAggregator,LTContainer,LTTextBox,LTText

from pdf import PDF

def extract(item):
    temp = []
    if isinstance(item,LTContainer):
        for child in item:
            temp += extract(child) 
    elif isinstance(item,LTText):
        try:
            temp.append(item.get_text())
        except:
            temp.append((item.get_text(),0,0,0,0))
    if isinstance(item,LTTextBox):
        temp.append('\n')
    text = ''.join(i for i in temp if isinstance(i,basestring))
    return text

password = ''
print sys.argv
fp = open(sys.argv[1], 'rb')
parser = PDFParser(fp)
document = PDFDocument(parser)
document.initialize(password)
rsrcmgr = PDFResourceManager()
laparams = LAParams()
device = PDFPageAggregator(rsrcmgr, laparams=laparams)
interpreter = PDFPageInterpreter(rsrcmgr, device)


pdf = PDF(sys.argv[1],verbose=True)

page_no = 1
for page in PDFPage.create_pages(document):
    interpreter.process_page(page)
    # receive the LTPage object for the page.
    layout = device.get_result()
    for group in layout.groups:
        rect = [group.x0,group.y0,group.x1,group.y1]
        quad = [
                group.x0,group.y0,
                group.x1,group.y0,
                group.x1,group.y1,
                group.x0,group.y1
                ]
        pdf.add_annot_to_page(page_no,quad,rect)
    page_no += 1

try:
    pdf.save('annot_test.pdf')
except:
    print "err"
    pass
