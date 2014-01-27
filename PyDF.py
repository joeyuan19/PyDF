import sys, re
import pdf_utils
from pdf_utils import get_pdf_obj_type, PDFFormatError, PDFOperationError, assert_pdf_ext, parse_obj_id, pdf_type_to_str,stream_decode,pdf_obj_to_py_obj
from optparse import OptionParser



# Helper Method
def format_pos_number(n,padding_digits=10,pad_with='0'):
	return ''.join(pad_with for i in range(padding_digits-len(str(n))))+str(n) 

def format_gen_number(n,padding_digits=5,pad_with='0'):
	return format_pos_number(n,padding_digits,pad_with)

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
#	Class:
#		PDF
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
#	Description:
#		Handles the creation of a PDF object within Python
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
#	Goals:
#		Create PDF Class which can be used to dynamically
#			edit modify and create .pdf files.
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
#	To do:
#		[+] Highlighting
#			[+] Properly Adding Annotations
#		[ ] Text locating
#			[ ] Search functions
#		[ ] Objectify all of PDF
#		[ ] Meta Data
#		[ ] Decode Streams
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
#	Method Overview:
#		> __init__
#			Usage: PDF(filename)
#			- Class is initialized with a filename/filepath
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 

class PDFObject(object):
	def __init__(self,parent,content,*args,**kwargs):
		self.parent  = parent
		self.content = content
		try:
			matches = re.findall(r'(\d+) (\d+) obj',content)
			self.obj_id = int(matches[0][0])
			self.gen_id = int(matches[0][1])
		except:
			raise PDFOperationError("Attempt to create instance of PDFObject from non-pdf object")
		self.obj_type = get_pdf_obj_type(content)
		self.value = pdf_obj_to_py_obj(self)
	
	def __unicode__(self):
		return self.__str__()

	def __str__(self):
		return	"PDFObject of type: " + pdf_type_to_str(self.obj_type)
	
	def __repr__(self):
		return "<PDFObject from " + self.parent.__repr__() + " of type: " + pdf_type_to_str(self.obj_type) + " >"
	
	def position(self):
		return self.parent.get_position(self.obj_id)

	def has_attr(self,attr,value=None):
		if value is None:
			try:
				self.value['/Type']
				return True
			except:
				return False
		else:
			try:
				return self.value[attr] == value
			except:
				return False

	def attr(self,attr,value=None):
		if value is None:
			try:
				return self.value[attr]
			except:
				return None
		else:
			self.attrs[str(attr)] = value

class PDF:
	def __init__(self,filename,verbose=False,debug=False,vv=False):
		if debug: print "Creating PDF Object..."
		try:
			if debug: print "Reading File...",
			with open(filename,'rb') as f:
				self.content = ''.join(i for i in f)
			if debug: print "complete."
		except IOError:
			raise PDFOperationError("Unable to read file.  File may not exist or may be damaged")
		except:
			raise PDFOperationError("Unable to read file.  File may not exist or may be damaged")
		self.edited_objs = []
		self.debug = debug
		self.verbose = verbose or debug
		self.vv = vv
		self.filename = filename
		self._set_obj_ref()
		self._set_page_ref()
		if self.debug or self.verbose:
			print "PDF Object created from file:",self.filename
			self.print_info()

	def _set_obj_ref(self):
		if self.verbose or self.debug: print "Indexing PDF objects...",
		objs = re.findall(r'((\d+) (\d+) obj.*?endobj)',self.content,re.S)
		self.obj_ref = {}
		self.next_obj_id = -1
		self.next_gen_id = 0
		for i in objs:
			try:
				temp = int(i[1])
				self.obj_ref[str(temp)+"-"+i[2]] = PDFObject(self,i[0])
				self.next_obj_id = max(self.next_obj_id,temp)
				try:
					self.next_gen_id = max(int(i[2]),self.next_gen_id)
				except Exception as e:
					if self.debug:
						print "Error setting gen id",e
						print "value",i
						raise e
			except Exception as e:
				if self.debug:
					print "Error:",e
					print "setting object reference on",i[1]+"-"+i[2],":"
					print "\t",i[0].replace("\t","").replace("\n","\n\t")
					raise e
		self.next_obj_id += 1
		self.next_gen_id += 1
		if self.vv: print self.obj_ref
		if self.verbose or self.debug: print "complete:",len(self.obj_ref),"objects indexed."

	def _set_page_ref(self):
		if self.verbose or self.debug: print "Indexing Pages...",
		root = re.findall(r'trailer.*?/Root.*?(\d+) 0 R',self.content,re.S)
		if len(root) <= 0:
			raise PDFFormatError(self.filename + " does not have a /Root.  The file may be damaged and pages cannot be indexed.")
		self.root = self.get_obj(root[-1])
		catalog = self.root.attr('/Pages') 
		if catalog is None:
			raise PDFFormatError(self.filename + " does not have a /Catalog.  The file may be damaged and pages cannot be indexed.")
		print catalog
		catalog = self.get_obj(catalog)
		pages = re.findall(r'/Kids.*?\[(.*?)\]',catalog.content,re.S)
		if len(pages) <= 0:
			raise PDFFormatError(self.filename + " does have a /Pages Object with a valid /Kids array.  File may be damaged and cannot be indexed.")
		pages = [i for i in re.findall('(\d+) \d+ R',pages[0])]
		page_list = [] 
		i = 0
		while i < len(pages):
			cur_page = pages[i]
			obj_type = self.get_obj_type(cur_page)
			try:
				if obj_type == pdf_utils.PDF_TYPE_DICT:
					obj = self.get_obj(cur_page)
					if obj.has_attr('/Type','/Pages'):
						pages_to_add = self._get_kids(cur_page)
						for j in range(len(pages_to_add)):
							pages.insert(i+1+j,pages_to_add[j])
					elif obj.has_attr('/Type','/Page'):
						page_list.append(cur_page)
					else:
						raise PDFFormatError("")
			except PDFFormatError:
				print "Warning: Object " + cur_page + " was found not to be of /Type /Page or /Type /Pages and is therefore invalid for indexing. File may be damaged..."	
				print obj.content,obj.value,obj.has_attr('/Type','/Pages')
			finally:
				i += 1
		if len(page_list) <= 0:
			raise PDFFormatError("Document was unable to be indexed.  The format could be damaged as a proper indexing could not be performed.")
		self.page_ref = {}
		for i in range(len(page_list)):
			self.page_ref[i+1] = page_list[i]
		if self.verbose or self.debug: print "complete:",len(self.page_ref),"pages indexed."
		return
	
	def _get_kids(self,pages_obj_id):
		obj = self.get_obj(pages_obj_id)
		kids = obj.attr('/Kids')
		return kids
	
	# Retrieve the next available object number 
	def get_next_obj_id(self,inc=True):
		obj_id = self.next_obj_id
		if inc:
			self.next_obj_id += 1 
		return obj_id

	def get_next_gen_id(self):
		return self.next_gen_id

	def get_obj_type(self,obj_id):
		return get_pdf_obj_type(self.get_obj(obj_id))

	def get_obj(self,obj_id):
		try:
			if isinstance(obj_id,basestring):
				match = re.findall(r'(\d+)( (\d+)? (R|obj)?)?',obj_id)
				if len(match) > 0:
					obj_id = match[0][0]
			return self.obj_ref[int(obj_id)]
		except KeyError:
			raise PDFOperationError("The file " + self.filename + " does not contain an object numbered " + str(obj_id))
		except ValueError:
			raise PDFOperationError("The object number " + str(obj_id) + " is not valid.  Object numbers must be positive integers.")
		except:
			raise

	def get_obj_count(self):
		return len(self.obj_ref)

	def get_page_obj_id(self,page_no):
		try:
			return self.page_ref[int(page_no)]
		except ValueError:
			raise PDFOperationError("The page number '" + str(page_no) + "' provided is not a valid page number.")
		except KeyError:
			raise PDFOperationError("The page number '" + str(page_no) + "' does not exist.")
	
	def get_page_count(self):
		return len(self.page_ref)
	
	def get_page_range(self):
		return range(1,self.get_page_count()+1)

	def get_annot_count(self):
		return self._get_type_count('/Annot')	

	def _get_type_count(self,attr_type):
		count = 0
		for obj_id in self.obj_ref:
			if self.obj_ref[obj_id].attr('/Type') == attr_type:
				count += 1
		return count

	def test(self):
		#self.annot_test()
		self.text_test()

	def annot_test(self):
		quad = [ 102.5784, 719.94, 113.9088, 719.94, 102.5784, 705.876, 113.9088, 705.876 ]
		rect = [ 102.5784, 705.876, 113.9088, 719.94 ]
		for i in range(1,self.get_page_count()+1):
			print "Annotating page",i
			annot_id,annot = self._create_annotation(rect,quad)
			self.edited_objs.append((annot,annot_id))
			self._add_annot_to_page(i,annot_id)
		self.save('annot_test_output.pdf')

	def _add_annot_to_page(self,page_no,annot_obj_id,overwrite=False):
		page_id = self.get_page_obj(page_no)
		page = self.get_obj(page_id)
		if "/Annots" in page:
			cur_value = re.findall(r'/Annots\s+(.*?)[/>]',page)
			if len(cur_value) > 0:
				cur_value = cur_value[0]
				cur_value_type = get_pdf_obj_type(cur_value)
				if cur_value_type == pdf_utils.PDF_TYPE_ARRAY:
					edited_page = re.sub(r'(/Annots\s+)\[(.*?)\]([/>])','\g<1>[\g<2> ' + str(annot_obj_id) + ' 0 R ]\g<3>',page)
					self.edited_objs.append((edited_page,page_id))
					return
				elif cur_value_type == pdf_utils.PDF_TYPE_REF:
					ref_obj = self.get_obj(cur_value)
					ref_obj_type = get_pdf_obj_type(ref_obj)
					if ref_obj_type == pdf_utils.PDF_TYPE_DICT and "/Annot" in ref_obj:
						edited_page = re.sub(r'(/Annots\s+)(.*?)([/>])','\g<1>[ \g<2> ' + str(annot_obj_id) + ' 0 R ]\g<3>',page)	
						self.edited_objs.append((edited_page,page_id))
						return
					elif ref_obj_type == pdf_utils.PDF_TYPE_ARRAY:
						ref_obj_id = parse_obj_id(ref_obj)
						edited_ref_obj = re.sub(r'(.*)\s+\]','\g<1> ' + str(annot_obj_id) + ' 0 R ]',ref_obj)
						self.edited_objs.append((edited_ref_obj,ref_obj_id))
						return
				else:
					print "else1"
			else:
				print "derp"
		else:
			new_arr_obj_id,new_arr_obj = self._create_new_arr_obj(values=[str(annot_obj_id)+" 0 R"])
			self.edited_objs.append((new_arr_obj,new_arr_obj_id))
			edited_page = re.sub('>>','/Annots ' + str(new_arr_obj_id) + ' 0 R >>',page)
			self.edited_objs.append((edited_page,page_id))
			return

	def _create_new_arr_obj(self,obj_id=None,values=[]):
		if obj_id is None:
			obj_id = self.get_next_obj_id()
		try:
			obj_id = str(obj_id)
		gen_id = self.get_next_gen_id()
		except:
			raise PDFOperationError("Invalid object id provided: " + obj_id)
		arr_obj = str(obj_id) + " " + str(gen_id) + " obj\n[ "
		for i in values:
			arr_obj += str(i) + " "
		arr_obj += "]\nendobj"
		self.obj_ref[obj_id] = arr_obj
		return obj_id,arr_obj

	def _create_annotation(self,rect,quad,color=None,obj_id=None):
		if obj_id is None:
			obj_id = self.get_next_obj_id()
		if color is None or len(color) < 3:
			# Default 'Highlighter Yellow'
			color = [ 0.9686242, 0.8626859, 0.03784475 ]
		annot = str(obj_id) + " " + str(self.get_next_gen_id()) + " obj\n<< /Type/Annot\n/Rect[ "
		annot += ' '.join(str(i) for i in rect)
		annot += " ]\n/F 4\n/C[ "
		annot += ' '.join(str(i) for i in color)
		annot += " ]\n/QuadPoints[ "
		annot += ' '.join(str(i) for i in quad)
		annot += " ]\n/Subtype /Highlight >>\nendobj"
		self.obj_ref[obj_id] = annot
		return obj_id,annot

	def text_test(self):
		for i in self.get_page_range():
			print "\n\nPage",i,"\n"
			self.get_page_text(i)

	def get_page_text(self,page_no):
		page_id = self.get_page_obj_id(page_no)
		page = self.get_obj(page_id)
		contents = re.findall(r'/Contents(.*)[/>]',page)
		if len(contents) > 0:
			stream = self.get_obj(contents[0].strip())
			filters = re.findall(r'/Filter(\s+)?((?P<bracket>\[)?/.*?(?(bracket)\]|[ >/]))',stream,re.S)
			print filters
			if len(filters) > 0:
				filters = filters[0][1].strip()
				if filters.endswith('/') or filters.endswith('>'):
					filters = filters[:-1]
			if get_pdf_obj_type(filters) == pdf_utils.PDF_TYPE_ARRAY:
				filters = filters.split(' ')
			print filters
			stream = re.findall(r'stream\s+(.*)\s+endstream',stream,re.S)
			if len(stream) > 0:
				stream = stream[0]
				pdf_stream_decode(stream,filters=[])

	def _apply_edits(self):
		xref = "xref\n0 1\n0000000000 65535 f\n"
		for edit in self.edited_objs:
			xref += str(edit[1]) + " 1\n"
			xref += str(format_pos_number(len(self.content))) + " " + str(format_gen_number(self.get_next_gen_id())) + " n\n"
			self.content += str(edit[0]) + "\n"
		lastxref = re.findall(r'startxref\s+(\d+)',self.content)
		lastxref = lastxref[-1]
		xref += "trailer\n<< /Root " + self.root + " R /Size " + str(self.get_next_obj_id(False)-1) + " /Prev " + lastxref + " >>\nstartxref\n"
		xref += str(len(self.content)+5) + "\n%%EOF"
		self.content += xref
		self.next_gen_id += 1

	def save(self,filename=None):
		if filename is None:
			filename = self.filename
		filename = assert_pdf_ext(filename)
		self._apply_edits()
		with open(filename,'w') as f:
			f.write(self.content)
		if self.verbose or self.debug:
			print "Saved file to:",filename

	def __unicode__(self):
		msg = ""
		if self.verbose or self.debug:
			msg += "PDF Object Information"
			msg += "\n\tFilename:\t\t" + str(self.filename)
			msg += "\n\tNumber of pages:\t" + str(self.get_page_count())
			if self.vv:
				msg += "\nObject Ref:\n" +str(self.page_ref)
			msg += "\n\tNumber of Objects:\t" + str(self.get_obj_count())
			if self.vv:
				msg += "\nObject Ref:\n"+str(self.obj_ref)
			msg += "\n\tNext Object Number:\t" + str(self.get_next_obj_id(False))
		else:
			msg = self.__repr__() 
		return msg

	def __repr__(self):
		return "<PDF Object from '" + str(self.filename) + "' at " + str(hex(id(self))) + ">"
	
	def __str__(self):
		return self.__unicode__()

	def print_info(self):
		print self.__unicode__()

if __name__ == '__main__':
	parser = OptionParser()
	parser.add_option("-v","--verbose",dest="verbose",action="store_true",default=False)
	parser.add_option("-V","--very-verbose",dest="vv",action="store_true",default=False)
	parser.add_option("-d","--debug",dest="debug",action="store_true",default=False)
	(opts,args) = parser.parse_args()
	if opts.debug:
		print opts
	# input files
	tests = [ 'tests/' + i for i in ('test.pdf','test2.pdf','test3.pdf','short.pdf','alice.pdf')]	
	#tests = ['tests/test.pdf']
	
	if len(args) > 0:
		files = args
	else:
		files = tests
	for file in files :
		pdf = PDF(file,debug=opts.debug,verbose=opts.verbose,vv=opts.vv)
		print pdf.get_annot_count()


