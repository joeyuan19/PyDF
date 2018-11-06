import sys, re
from utils import * 
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
#	Ideas:
#		* PDF repair
#		* Regex search and highlight
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
#	To do:
#		[ ]	Add page
#		[ ] Write text content
#		[ ] Edit/Update objs
#		[-] Annotations
#			[+] Properly Adding Annotations
#			[+] Highlighting
#		[ ] Text locating
#			[ ] Search functions
#		[+] Objectify all of PDF
#		[ ] Meta Data
#		[-] Decode Streams
#			[+] /FlateDecode
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
#	Method Overview:
#		> __init__
#			Usage: PDF(filename)
#			- Class is initialized with a filename/filepath
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 

class PDFObject(object):
	def __init__(self,parent,content,is_trailer=False,register=False,*args,**kwargs):
		self.parent  = parent
		self.content = content
		self.is_trailer = is_trailer
		if not is_trailer:
			try:
				matches = re.findall(r'(\d+) (\d+) obj',content)
				self.obj_id = int(matches[0][0])
				self.gen_id = int(matches[0][1])
			except:
				raise PDFOperationError("Attempt to create instance of PDFObject from non-pdf object")
		self.obj_type = get_pdf_obj_type(content)
		self.value = pdf_obj_to_py_obj(self)
		if register and not is_trailer:
			self.parent.register(self)
	
	def __unicode__(self):
		return self.__str__()

	def __str__(self):
		return	"PDFObject of type: " + pdf_type_to_str(self.obj_type)
	
	def __repr__(self):
		return "<PDFObject from " + self.parent.__repr__() + " of type: " + pdf_type_to_str(self.obj_type) + " >"
	
	def get_obj_id(self):
		return str(self.obj_id)+"-"+str(self.gen_id)

	def indirect_ref(self):
		return str(self.obj_id)+" "+str(self.gen_id)+" R"

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
			self.value[attr] = value

	def optimize(self):
		self.parent._optimize(self,self.is_trailer)

	def to_pdf_obj(self):
		return py_obj_to_pdf_obj(self,PDFObject=PDFObject)

	def copy(self):
		return PDFObject(self.parent,self.content,is_trailer=self.is_trailer,register=True)

	def edit(self,action,value=None):
		copy = self.copy()
		if 'value' in action:
			if action == 'value_append':
				copy.value.append(value)
			elif action == 'value_add':
				copy.value[action] = value
			elif action == 'value_del':
				del(copy.value[action])
		elif action == 'set_trailer':
			copy.is_trailer = True
		elif action == 'gen_id':
			copy.gen_id = value
		elif action == 'obj_id':
			copy.obj_id = value
		elif action == 'content':
			copy.content = value
			copy.obj_type = get_pdf_obj_type(copy.content)
		else:
			copy.value[action] = value
		return copy
	

class PDF:
	def __init__(self,filename,verbose=False,debug=False,vv=False):
		'''initialization of PDF object, with verbose,debug,vv (very verbose),
		options for levels of printed output information, generally I imagine these
		will rarely be called when not being used as a command line tool.  Takes a
		filename/path as an argument, reads the doc and attempts to create a PDF
		object out of the file, calls all initialization methods, setting page
		reference and object reference'''
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

	# Note: May want to account for broken PDF objects
	def _set_obj_ref(self):
		'''set the object reference dictionary, and turn all PDF objects into python
		objects.  This method ignores non-valid PDF objects'''
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
		if self.verbose or self.debug: print "complete:",len(self.obj_ref),"objects indexed."
		if self.verbose or self.debug: print "Optimizing PDFObject links...",
		c = self._optimize_obj_ref()
		if self.verbose or self.debug: print "complete.",c,"links optimized."
	
	def _optimize_obj_ref(self):
		'''wrapper method to optimize all existing objs in PDF, used during
		initialization'''
		opt_count = 0
		for obj_id in self.obj_ref:	
			opt_count += self._optimize(self.obj_ref[obj_id],obj_id=obj_id)
		return opt_count

	def _optimize(self,obj,obj_id=None,is_trailer=False):
		'''Optimize the links between PDFObjects, PDFs use indirect references which
		work well in their own frame, but here it is better to link directly to the
		object.'''
		count = 0
		if not is_trailer and obj_id is None:
			obj_id = obj.get_obj_id()
		value = obj.value
		if isinstance(value,basestring) and get_pdf_obj_type(value) == PDF_TYPE_REF:
			self.obj_ref[obj_id].value = self.get_obj(value)
			count += 1
		elif isinstance(value,dict):
			for attr in value: 
				if isinstance(value[attr],basestring) and get_pdf_obj_type(value[attr]) == PDF_TYPE_REF:
					if is_trailer:
						self.trailer.attr(attr,self.get_obj(value[attr]))
						count += 1
					else:
						self.obj_ref[obj_id].attr(attr,self.get_obj(value[attr]))
						count += 1
		elif isinstance(value,list):
			for item,i in enumerate(value):
				if isinstance(item,basestring) and get_pdf_obj_type(item) == PDF_TYPE_REF:
					self.obj_ref[obj_id].value[i] = self.get_obj(item)
					count += 1
		return count	

	def register(self,obj):
		'''set up a new object within an existing PDF, including indexing, and 
		optimizing links to other objects'''
		self.obj_ref[obj.get_obj_id()] = obj
		self._optimize(obj)

	def _set_page_ref(self):
		'''set up a dictionary for refernce to pages by their number'''
		if self.verbose or self.debug: print "Indexing Pages...",
		trailer = re.findall(r'trailer(.*?)startxref',self.content,re.S)
		if len(trailer) <= 0:
			raise PDFFormatError(r'PDF does not contain a trailer, file may be damaged')
		self.trailer = PDFObject(self,trailer[-1],is_trailer=True,optimize=True)
		root = self.trailer.attr('/Root')
		if root is None:
			raise PDFFormatError(self.filename + " does not have a /Root.  The file may be damaged and pages cannot be indexed.")
		self.root = self.get_obj(root)
		catalog = self.root.attr('/Pages') 
		if catalog is None:
			raise PDFFormatError(self.filename + " does not have a /Catalog.  The file may be damaged and pages cannot be indexed.")
		pages = catalog.attr('/Kids')
		if len(pages) <= 0:
			raise PDFFormatError(self.filename + " does have a /Pages Object with a valid /Kids array.  File may be damaged and cannot be indexed.")
		page_list = [] 
		i = 0
		while i < len(pages):
			cur_page = pages[i]
			obj_type = self.get_obj_type(cur_page)
			try:
				if obj_type == PDF_TYPE_DICT:
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
		'''get the kids of /Pages object'''
		obj = self.get_obj(pages_obj_id)
		kids = obj.attr('/Kids')
		return kids
	
	# Retrieve the next available object number 
	def get_next_obj_id(self,inc=True):
		'''get the next available object id'''
		obj_id = self.next_obj_id
		if inc:
			self.next_obj_id += 1 
		return obj_id

	def get_next_gen_id(self):
		'''get the next generation number'''
		return self.next_gen_id

	def get_obj_type(self,obj_id):
		'''determine the object type for object with object id <obj_id>'''
		if isinstance(obj_id,PDFObject):
			obj_id = obj_id.obj_id
		return get_pdf_obj_type(self.get_obj(obj_id))

	def get_obj(self,obj_id,gen_id=0):
		'''return the PDFObject that is indexed by the gen id'''
		try:
			if isinstance(obj_id,basestring):
				match = re.findall(r'(\d+)( (\d+)? (R|obj)?)?',obj_id)
				if len(match) > 0:
					obj_id = match[0][0]
					if len(match[0][2]) > 0:
						gen_id = match[0][2]
			return self.obj_ref[str(obj_id)+'-'+str(gen_id)]
		except KeyError:
			raise PDFOperationError("The file " + self.filename + " does not contain an object numbered " + str(obj_id))
		except ValueError:
			raise PDFOperationError("The object number " + str(obj_id) + " is not valid.  Object numbers must be positive integers.")
		except:
			raise

	def get_obj_count(self):
		'''get the number of objects contained in the pdf document'''
		return len(self.obj_ref)

	def get_page(self,page_no):
		'''get the PDFObject for page number <page_no>'''
		return self.get_obj(self.get_page_obj_id(page_no))

	def get_page_obj_id(self,page_no):
		'''get the obj_id of the <page_no>th page'''
		try:
			return self.page_ref[int(page_no)]
		except ValueError:
			raise PDFOperationError("The page number '" + str(page_no) + "' provided is not a valid page number.")
		except KeyError:
			raise PDFOperationError("The page number '" + str(page_no) + "' does not exist.")
	
	def get_page_count(self):
		'''get number of pages in the document'''
		return len(self.page_ref)
	
	def get_page_range(self):
		'''return the range of pages, useful to avoid 0/1 indexing confusion'''
		return range(1,self.get_page_count()+1)

	def get_annot_count(self):
		'''get the number of annotations contained in the document'''
		return self._get_type_count('/Annot')

	def _get_type_count(self,attr_type):
		'''get the count of objects of type <attr_type>'''
		count = 0
		for obj_id in self.obj_ref:
			if self.obj_ref[obj_id].attr('/Type') == attr_type:
				count += 1
		return count


	# ADD ANNOTATION TO A PAGE

	def _add_annot_to_page(self,page_no,annot,overwrite=False):
		'''add an annotation to a page'''
		page_id = self.get_page_obj_id(page_no)
		page = self.get_page(page_no)
		cur_value = page.attr('/Annots')
		if cur_value is not None:
			if isinstance(cur_value,list):
				edited_page = page.edit('/Annots',cur_value.append(annot))
				self.edited_objs.append(edited_page)
				return
			elif isinstance(cur_value,PDFObject): 
				if cur_value.obj_type == PDF_TYPE_DICT and cur_value.has_attr('/Annot'):
					edited_page = page.edit('/Annots',[cur_value,annot])
					self.edited_objs.append(edited_page)
					return
				elif cur_value.obj_type == PDF_TYPE_ARRAY:
					edited_arr = cur_value.edit('value',cur_value.value.append(annot))	
					self.edited_objs.append(edited_arr)
					return
		else:
			new_arr_obj = self.create_new_arr_obj(values=[annot])
			self.edited_objs.append(new_arr_obj)
			edited_page = page.edit('/Annots',new_arr_obj)
			self.edited_objs.append(edited_page)
			return

	# OBJECT CREATION METHODS 

	def create_new_arr_obj(self,obj_id=None,values=[]):
		'''create a PDFObject of type array, with the given values'''
		if obj_id is None:
			obj_id = self.get_next_obj_id()
		try:
			obj_id = str(obj_id)
		except:
			raise PDFOperationError("Invalid object id provided: " + obj_id)
		gen_id = self.get_next_gen_id()
		arr_obj = str(obj_id) + " " + str(gen_id) + " obj\n[ "
		for i in values:
			if isinstance(i,PDFObject):
				arr_obj += str(i.indirect_ref()) + " "
			else:
				arr_obj += py_obj_to_pdf_obj(i,PDFObject) + " "	
		arr_obj += "]\nendobj"
		new_arr_obj = PDFObject(self,arr_obj,register=True)
		return new_arr_obj 


	# Notes: May want to expand this to accept all parameters for annotations
	def _create_annotation(self,rect,quad,color=None,obj_id=None):
		'''Create a new annotation object'''
		if obj_id is None:
			obj_id = self.get_next_obj_id()
		gen_id = self.get_next_gen_id()
		if color is None or len(color) < 3:
			# Default 'Highlighter Yellow'
			color = [ 0.9686242, 0.8626859, 0.03784475 ]
		annot = str(obj_id) + " " + str(gen_id) + " obj\n<< /Type/Annot\n/Rect[ "
		annot += ' '.join(str(i) for i in rect)
		annot += " ]\n/F 4\n/C[ "
		annot += ' '.join(str(i) for i in color)
		annot += " ]\n/QuadPoints[ "
		annot += ' '.join(str(i) for i in quad)
		annot += " ]\n/Subtype /Highlight >>\nendobj"
		annot_obj = PDFObject(self,annot,register=True)
		return annot_obj 
	
	# Note: May want to have a decode_page method,
	#       and call for each page here instead 
	def decode_pdf(self):
		'''decode entire document into plain text'''
		for i in self.obj_ref:
			if self.obj_ref[i].obj_type == pdf_utils.PDF_TYPE_STREAM:
				pass

	# Note: - May want to structure this in a format that is navigable
	# 		- get_document_text, by paragraph?, by aribitrarily sized string length?
	def get_page_text(self,page_no):
		'''Get Text content from a single page'''
		page_id = self.get_page_obj_id(page_no)
		page = self.get_obj(page_id)
		contents = page.attr('/Contents')
		print contents


	def _apply_edits(self):
		'''apply unsaved changes to the docuemnt'''
		xref = "xref\n0 1\n0000000000 65535 f\n"
		for edit in self.edited_objs:
			xref += str(edit.obj_id) + " 1\n"
			xref += str(format_pos_number(len(self.content))) + " " + str(format_gen_number(self.get_next_gen_id())) + " n\n"
			self.content += edit.to_pdf_obj() + "\n"
		lastxref = re.findall(r'startxref\s+(\d+)',self.content)
		lastxref = lastxref[-1]
		new_trailer = self.trailer.edit('/Prev',int(lastxref))
		new_trailer.attr('/Size',self.get_next_obj_id(False)-1)
		xref += new_trailer.to_pdf_obj()
		xref += "\nstartxref\n"
		xref += str(len(self.content)+5) + "\n%%EOF"
		self.content += xref
		self.next_gen_id += 1

	# SAVE
	
	def save(self,filename=None):
		'''save the file to the given filename or the original filename by default'''
		if filename is None:
			filename = self.filename
		filename = assert_pdf_ext(filename)
		self._apply_edits()
		with open(filename,'w') as f:
			f.write(self.content)
		if self.verbose or self.debug:
			print "Saved file to:",filename

	# TO STRING METHODS
	
	def __unicode__(self):
		'''detailed to string method for verbose/debugging usage'''
		msg = ""
		if self.verbose or self.debug:
			msg += "PDF Object Information"
			msg += "\n\tFilename:\t\t" + str(self.filename)
			msg += "\n\tNumber of pages:\t" + str(self.get_page_count())
			if self.vv:
				msg += "\nPage Ref:\n" +str(self.page_ref)
			msg += "\n\tNumber of Objects:\t" + str(self.get_obj_count())
			if self.vv:
				msg += "\nObject Ref:\n"+str(self.obj_ref)
			msg += "\n\tNext Object Number:\t" + str(self.get_next_obj_id(False))
			msg += "\n\tNext Generation Number:\t" + str(self.get_next_gen_id())
		else:
			msg = self.__repr__() 
		return msg

	def __repr__(self):
		'''straight-forward representation'''
		return "<PDF from '" + str(self.filename) + "' at " + str(hex(id(self))) + ">"
	
	def __str__(self):
		'''same as __unicode__'''
		return self.__unicode__()

	def print_info(self):
		'''prints __unicode__'''
		print self.__unicode__()
	
	# TESTS

	def test(self):
		self.annot_test()
		#self.text_test()
		#self.stream_test()
		self.stringify_test()
	
	def text_test(self):
		'''print the text content of every page'''
		for i in self.get_page_range():
			self.get_page_text(i)

	def stringify_test(self):
		'''print the to_pdf_obj method of every object'''
		for obj_id in self.obj_ref:
			print self.obj_ref[obj_id].to_pdf_obj()

	def annot_test(self):
		'''apply an arbitrary annotation to every page'''
		quad = [ 102.5784, 719.94, 113.9088, 719.94, 102.5784, 705.876, 113.9088, 705.876 ]
		rect = [ 102.5784, 705.876, 113.9088, 719.94 ]
		for i in range(1,self.get_page_count()+1):
			print "Annotating page",i
			annot = self._create_annotation(rect,quad)
			self.edited_objs.append(annot)
			self._add_annot_to_page(i,annot)
		self.save('annot_test_output.pdf')

if __name__ == '__main__':
	parser = OptionParser()
	parser.add_option("-v","--verbose",dest="verbose",action="store_true",default=False)
	parser.add_option("-V","--very-verbose",dest="vv",action="store_true",default=False)
	parser.add_option("-d","--debug",dest="debug",action="store_true",default=False)
	(opts,args) = parser.parse_args()
	if opts.debug: print opts
	
	if len(args) > 0:
		files = args
	else:
		print "No Argument provided. Usage:"
		print "\tPyDF.py [-vVd] [--debug] [--very-verbose] [--debug] file1.pdf file2.pdf [...]"
		print "\tDoes not do much from the command line at the present time"
		print "\t  but the classes can be used to explore PDF objects and structure"
		sys.exit(1)

	for file in files:
		pdf = PDF(file,debug=opts.debug,verbose=opts.verbose,vv=opts.vv)


