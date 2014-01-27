#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import zlib
class PDFFormatError(Exception):
	pass

class PDFOperationError(Exception):
	pass

PDF_TYPE_REF = 0
PDF_TYPE_NUM = 1
PDF_TYPE_NULL = 2
PDF_TYPE_BOOL = 3
PDF_TYPE_ARRAY = 4
PDF_TYPE_DICT = 5
PDF_TYPE_STREAM = 6
PDF_TYPE_STRING = 7
PDF_TYPE_NAME = 8

PDF_DELIMETERS = ['{','}','(',')','<','>','[',']','{','}','/','%']

def pdf_type_to_str(obj_type):
	types = {
		0 : 'Reference',
		1 : 'Numeric',
		2 : 'Null',
		3 : 'Boolean',
		4 : 'Array',
		5 : 'Dictionary',
		6 : 'Stream',
		7 : 'String',
		8 : 'Name',
	}
	try:
		return types[obj_type]
	except:
		return "TYPE NOT FOUND"

def get_pdf_obj_type(obj):
	try:
		content = obj.content
	except:
		content = obj
	return _get_pdf_obj_type(content)

def _get_pdf_obj_type(obj):
	if not isinstance(obj,basestring):
		raise PDFOperationError('Invalid PDF object: ' + str(obj))
	obj = debone_pdf(get_obj_content(obj))
	try:
		float(obj)
		return PDF_TYPE_NUM
	except:
		# Check for Object reference: OBJECT_NO 0 R
		obj_type = re.findall(r'^\d+ \d+ R$',obj)
		if len(obj_type) > 0:
			return PDF_TYPE_REF
		# Check for Array: [ ... ] 
		obj_type = re.findall(r'^\[.*\]$',obj)
		if len(obj_type) > 0:
			return PDF_TYPE_ARRAY
		# Check for String: ( ... )
		obj_type = re.findall(r'^\(.*\)$',obj)
		if len(obj_type) > 0:
			return PDF_TYPE_STRING
		# Check for Dictionary: << ... >>
		obj_type = re.findall(r'^(\<\<.*\>\>)$',obj)
		if len(obj_type) > 0:
			return PDF_TYPE_DICT
		# Check for Stream:
		obj_type = re.findall(r'^\<\<.*\>\>\s+?stream.*endstream',obj,re.S)
		if len(obj_type) > 0:
			return PDF_TYPE_STREAM
		# Check for String: < ... >
		obj_type = re.findall(r'^(\<.*\>)$',obj)
		if len(obj_type) > 0:
			return PDF_TYPE_STRING
		# Check for boolean: true
		obj_type = re.findall(r'^true$',obj)
		if len(obj_type) > 0:
			return PDF_TYPE_BOOL
		# Check for boolean: false 
		obj_type = re.findall(r'^false$',obj)
		if len(obj_type) > 0:
			return PDF_TYPE_BOOL
		# Check for null: null 
		obj_type = re.findall(r'^null$',obj)
		if len(obj_type) > 0:
			return PDF_TYPE_NULL
		# Check for name: /...
		obj_type = re.findall(r'^/.*?$',obj)
		if len(obj_type) > 0:
			return PDF_TYPE_NAME
	raise PDFOperationError('Invalid PDF object: ' + str(obj)  )
	
def py_obj_to_pdf_obj(py_obj):
	t = type(py_obj)
	if isinstance(py_obj,basestring):
		pass
	if t is str:
		pass

def pdf_obj_to_py_obj(pdf_obj):
	obj_type = pdf_obj.obj_type
	content = pdf_obj.content
	return _pdf_obj_to_py_obj(content,obj_type=obj_type)

def _pdf_obj_to_py_obj(pdf_obj,obj_type=None):
	if obj_type is None:
		obj_type = _get_pdf_obj_type(pdf_obj)
	pdf_obj = get_obj_content(pdf_obj)
	value = None
	if obj_type == PDF_TYPE_DICT:
		value = pdf_dict_to_py_dict(pdf_obj)
	elif obj_type == PDF_TYPE_ARRAY:
		value = pdf_array_to_py_array(pdf_obj)
	elif obj_type == PDF_TYPE_NUM:
		value = pdf_num_to_py_num(pdf_obj)
	elif obj_type == PDF_TYPE_STREAM:
		value = pdf_stream_to_py_dict(pdf_obj)
	elif obj_type == PDF_TYPE_REF:
		value = pdf_ref_to_py_str(pdf_obj)
	elif obj_type == PDF_TYPE_BOOL:
		value = pdf_bool_to_py_bool(pdf_obj)
	elif obj_type == PDF_TYPE_NAME:
		value = pdf_name_to_py_str(pdf_obj)
	elif obj_type == PDF_TYPE_NULL:
		return None	
	else:
		value = pdf_obj
	if value is None:
		raise PDFOperationError("Invalid obj format: '"+str(pdf_obj)+"' of type '" + pdf_type_to_str(obj_type) + "'")
	else:
		return value

def parse_obj_id(obj):
	matches = re.findall(r'(\d+ \d+) (R|obj)',obj)
	if len(matches) > 0:
		try:
			return int(matches[0][0])
		except:
			pass
	return None

def get_obj_content(obj):
	matches = re.findall(r'obj(.*)endobj',obj,re.S)
	if len(matches) > 0:
		return matches[0].strip()
	return obj

def pdf_ref_to_py_str(ref):
	return ref

def pdf_name_to_py_str(string):
	return string

def pdf_num_to_py_num(num):
	try:
		content = get_obj_content(num)
		if content is not None:
			num = content
		try:
			return int(num)
		except:
			return float(num)
	except:
		return None

def pdf_bool_to_py_bool(boolean):
	try:
		content = get_obj_content(boolean)
		if content is not None:
			boolean = content
		return boolean == "true"
	except:
		return None

def pdf_array_to_py_array(a):
	try:
		content = get_obj_content(a)
		if content is not None:
			a = content
		a = a.strip()
		if a.startswith('[') and a.endswith(']'):
			a = a[1:-1]
		a = debone_pdf(a)
		if len(a) == 0:
			return []
		a = a.split(' ')
		py_a = []
		buf = []
		while len(a) > 0:
			if a[0].startswith('('):
				while len(buf) > 0:
					py_a.append(_pdf_obj_to_py_obj(buf[0]))
					buf = buf[1:]
				str_buf = ''
				while len(a) > 0:
					str_buf += a[0] + ' '
					a = a[1:]
					if str_buf.endswith(') '):
						str_buf = str_buf[:-1]
						break
				py_a.append(_pdf_obj_to_py_obj(str_buf))
			elif a[0].startswith('['):
				while len(buf) > 0:
					py_a.append(_pdf_obj_to_py_obj(buf[0]))
					buf = buf[1:]
				str_buf = ''
				depth_count = 0
				while len(a) > 0:
					str_buf += a[0] + ' '
					if a[0].startswith('['):
						depth_count += 1
					if str_buf.endswith('] '):
						depth_count += -1
					a = a[1:]
					if depth_count == 0:
						break
				py_a.append(_pdf_obj_to_py_obj(str_buf))
			elif a[0].startswith('<<'):
				while len(buf) > 0:
					py_a.append(_pdf_obj_to_py_obj(buf[0]))
					buf = buf[1:]
				str_buf = ''
				depth_count = 0
				while len(a) > 0:
					str_buf += a[0] + ' '
					if a[0].startswith('<<'):
						depth_count += 1
					if str_buf.endswith('>> '):
						depth_count += -1
					a = a[1:]
					if depth_count == 0:
						str_buf = str_buf[:-1]
						break
				py_a.append(_pdf_obj_to_py_obj(str_buf))
			elif a[0].startswith('<'):
				while len(buf) > 0:
					py_a.append(_pdf_obj_to_py_obj(buf[0]))
					buf = buf[1:]
				str_buf = ''	
				while len(a) > 0:
					str_buf += a[0] + ' '
					a = a[1:]
					if str_buf.endswith('> '):
						str_buf = str_buf[:-1]
						break
			else:
				buf.append(a[0])
				if len(buf) >= 3:
					t = ' '.join(i for i in buf)
					if buf[-1] == 'R' and _get_pdf_obj_type(t) == PDF_TYPE_REF:
						py_a.append(_pdf_obj_to_py_obj(t))
						buf = []
					else:
						py_a.append(_pdf_obj_to_py_obj(buf[0]))
						buf = buf[1:]
				a = a[1:]
		while len(buf) > 0:
			py_a.append(_pdf_obj_to_py_obj(buf[0]))
			buf = buf[1:]
		return py_a
	except Exception as e:
		return None

def pdf_dict_to_py_dict(d):
	for delimeter in PDF_DELIMETERS:
		d = d.replace(delimeter,' '+delimeter)
	d = d.replace('< <','<<')
	d = d.replace('> >','>>')
	d = debone_pdf(d)
	if d.startswith('<<') and d.endswith('>>'):
		d = d[2:-2]
	py_a = pdf_array_to_py_array(d)
	py_d = {}
	for i in range(0,len(py_a),2):
		py_d[py_a[i]] = py_a[i+1]
	return py_d		

def pdf_stream_to_py_dict(s):
	d,s = splitstream(s)
	if len(s) <= 0:
		return None
	d = pdf_dict_to_py_dict(d)
	d['stream'] = re.findall(r'stream(.*)endstream',s,re.S)[0]
	filters = d['/Filter']
	d['stream_decoded'] = stream_decode(d['stream'],filters)
	return d

def iswhitespace(char):
	return len(char.strip()) == 0

def linearize_whitespace(string):
	temp = string.strip().replace('\n',' ').replace('\t',' ').replace('\r',' ')
	temp = re.sub(r'(\s){2,}',' ',temp)
	return temp

def debone_pdf(pdf_text):
	pdf_text,stream = splitstream(pdf_text)
	pdf_text = linearize_whitespace(remove_comments(pdf_text)).strip()
	if len(stream) > 0:
		return pdf_text + '\n' + stream.rstrip()
	else:
		return pdf_text 

def stream_decode(stream,filters):
	_stream = stream
	if isinstance(filters,basestring):
		_filter = filters
		print [_stream]
		if _filter == "/FlateDecode":
			print len(_stream.strip("\r").strip("\n"))
			_stream = zlib.decompress(_stream.strip("\r").strip("\n"))
		elif _filter == "/ASCIIHexDecode":
			_stream = binascii.unhexlify(_stream.replace("\r","").replace("\n","").replace(" ","").strip("<").strip(">"))
	else:
		for _filter in filters:
			_stream = stream_decode(_stream,_filter)
	return _stream


def remove_comments(pdf_text):
	return re.sub(r'%.*','',pdf_text)

def splitstream(pdf_text):
	temp = pdf_text.strip()
	stream_regex = re.compile(r'stream.*endstream$',re.S)
	index = -1
	for i in stream_regex.finditer(pdf_text):
		index = i.start()
	if index > 0:
		return pdf_text[:index],pdf_text[index:]
	else:
		return pdf_text,""

def assert_pdf_ext(filename):
	if filename.endswith('.pdf'):
		return filename
	else:
		return filename + '.pdf'


if __name__ == '__main__':
	test ="""
4 0 obj
<< /Length 5 0 R /Filter /FlateDecode >>
stream
x]Nª¬0‹˚«£%YRßØ¥+àÖ≠í%⁄)Ç©H%ˇ/ë&t €“˘d›ùgÙò°?ä|ï®[£L”xﬂq≈˘…iX
Ì¨◊ê¢&ÚeÈÜZUWâùp‰ÂJ§¡E—ä<!g÷J√ü∏Al∂ªΩÙL§ŸaÉL%F%9sxÓ7HWÖ2]˘MCL[ΩW¸ÀôL¯â‡◊ Ó∫1Ò
endstream
endobj
"""

	compare = """\nx\x01]N\xbb\x0e\xc20\x0c\xdc\xfb\x15\xc7\xa3%YR\xa7\xaf\xb4+\x88\x85\xad\x92%\x06\xda)\x82\x01\xa9H%\xff/\x91&t\x00\xdb\xd2\xf9d\xdd\x9dg\xf4\x98\xa1\x0b?\x8a|\x95\xa8[\xa3L\x03\xd3\x04x\xdfq\xc5\x0b\xf9\xc9iX\x07\n\xed\xac\xd7\x90\xa2&\xf2e\xe9\x08\x86ZUW\x89\x9dp\xe4\xe5J\xa4\xc1\x16\x05E\xd1\x8a<!g\xd6J\xc3\x9f\x1f\xb8Al\xb6\xbb\xbd\xf4L\xa4\xd9a\x10\x83L%F\xf0%9sx\xee7HW\x852]\xf9MCL[\xbdW\xfc\xcb\x10\x99L\xf8\x89\xe0\xd7\x7f\x00\xee\xba1\xf1\n"""

	print len(compare)

	print "Object to test:",[test]
	print "Object Length:",len(test)
	print
	print _pdf_obj_to_py_obj(test)

