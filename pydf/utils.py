#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import zlib

class PDFFormatError(Exception):
	pass

class PDFOperationError(Exception):
	pass

PDF_TYPE_INVALID = -1
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
	return PDF_TYPE_INVALID
	
def py_obj_to_pdf_obj(py_obj,obj_type=None,PDFObject=None):
	if PDFObject is not None:
		if isinstance(py_obj,PDFObject):
			if py_obj.is_trailer:
				pdf_obj = "trailer\n"+_py_obj_to_pdf_obj(py_obj.value)
			else:
				pdf_obj = str(py_obj.obj_id) + ' ' + str(py_obj.gen_id) + ' obj\n'
				pdf_obj += _py_obj_to_pdf_obj(py_obj.value) + '\n'
				pdf_obj += 'endobj'
		else:
			pdf_obj = _py_obj_to_pdf_obj(py_obj)
	else:
		pdf_obj = _py_obj_to_pdf_obj(py_obj)
	return pdf_obj
		

def _py_obj_to_pdf_obj(py_obj):
	if isinstance(py_obj,dict):
		if 'stream' in py_obj:
			pdf_obj = py_dict_to_pdf_stream(py_obj)
		else:
			pdf_obj = py_dict_to_pdf_dict(py_obj)
	elif isinstance(py_obj,list):
		pdf_obj = py_array_to_pdf_array(py_obj)
	elif isinstance(py_obj,bool):
		pdf_obj = py_bool_to_pdf_bool(py_obj)
	elif isinstance(py_obj,(int,float,complex,long)):
		pdf_obj = py_num_to_pdf_num(py_obj)
	elif isinstance(py_obj,basestring):
		pdf_obj = py_str_to_pdf_str(py_obj)
	else:
		try:
			pdf_obj = py_obj.indirect_ref()
		except:
			pdf_obj = str(py_obj)
	return pdf_obj

def py_dict_to_pdf_stream(py_dict):
	return py_dict_to_pdf_dict(py_dict,True)

def py_dict_to_pdf_dict(py_dict,is_stream=False):
	buf = "<< "
	for key in py_dict:
		if is_stream and key != 'stream' or key != 'stream_decoded':
			buf += key + " " + py_obj_to_pdf_obj(py_dict[key]) + " "
	buf += ">>"
	if is_stream:
		buf += "\nstream\n"
		buf += py_dict['stream'] + "\n"
		buf += "endstream"
	return buf

def py_array_to_pdf_array(py_arr):
	buf = "[ "
	for item in py_arr:
		buf += py_obj_to_pdf_obj(item) + " "
	buf += "]"
	return buf

def py_bool_to_pdf_bool(py_bool):
	if py_bool:
		return "true"
	else:
		return "false"

def py_num_to_pdf_num(py_num):
	return str(py_num)

def py_str_to_pdf_str(py_str):
	if py_str.startswith('<') and py_str.endswith('>'):
		return py_str
	elif py_str.startswith('(') and py_str.endswith(')'):
		return py_str
	elif py_str.startswith('/'):
		return py_str
	else:
		if get_pdf_obj_type(py_str) == PDF_TYPE_REF:
			return py_str
		return '(' + py_str + ')'

def pdf_obj_to_py_obj(pdf_obj):
	obj_type = pdf_obj.obj_type
	content = pdf_obj.content
	return _pdf_obj_to_py_obj(content,obj_type=None)

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
				py_a.append(_pdf_obj_to_py_obj(str_buf))
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
		if _filter == "/FlateDecode":
			_stream = zlib.decompress(_stream.strip("\r").strip("\n"))
		elif _filter == "/ASCIIHexDecode":
			_stream = binascii.unhexlify(_stream.replace("\r","").replace("\n","").replace(" ","").strip("<").strip(">"))
		else:
			print "other decode"
	else:
		for _filter in filters:
			_stream = stream_decode(_stream,_filter)
	return _stream


def remove_comments(pdf_text):
	return re.sub(r'%.*','',pdf_text)

def splitstream(pdf_text):
	temp = pdf_text.strip()
	stream_regex = re.compile(r'stream.*endstream',re.S)
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

if __name__ == '__main__':
	pass # used for testing
