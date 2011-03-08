#!/usr/bin/python

# dropbox
#
# dropbox - web file sharing
# By Jon Rifkin <jon.rifkin (at) uconn.edu>
# Copyright 2006-2007 Jonathan Rifkin
#
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
#
#
#  INTRODUCTION
#
#  This cgi script provides a large file sharing service.  Local and remote
#  users can upload and download files, but remote users can only download
#  files posted by local users.
#
#  Privacy is maintained by assigning a unique password with each uploaded
#  file.  After a file is uploaded, the user is shown a link which includes
#  the file name and password, and which can be sent to others to retrieve
#  the file (with the above mentioned restriction, remote users cannot
#  retreive files posted by other remote users).
#
#  Logging for uploading and downloading is down to file 'dropbox.log'
#  in the dropbox directory.
#
# Here are the steps taken by this script when uploading and downloading.
#
#    UPLOADING
#
#      (1) Present a file upload form.
#      (2) Upload file to the dropbox directory (see configuration below).
#      (3) Display the link used to retrieve the file.
#
#    DOWNLOADING
#
#       (1)  If invoked with a valid link, the file is sent to the browser.
#
#
#  CONFIGURATION
#
#  Configuration is done in the LOCAL CONFIGURATION section below.  The
#  configuration options are
#
#     YOUR_LOCATION  This is the name of your location used for display
#                    purposes only.
#
#     FILE_LIMIT   Maximum file size in MB (10^6 bytes).  This is the limit
#                  shown to the user, but the script allows a grace interval
#                  of 6.9%, which accounts for difference between decimal MB
#                  (10^6) and binary MB (2^20), with an addition 2% margin.
#
#    FILE_RETENTION  Number of days after which files are deleted.  This value
#                    is for display purposes only.  This script does not 
#                    delete the files; deletion must be done by a cron job
#                    or similar.
#
#    DROPBOX_BASE_DIR  This is the full path (such as '/home/dropbox') of the
#                      dropbox base directory.  The files/ and log/ directories
#            are stored under this.  This directory must be readable
#               and writable by the Web Server. 
#
#    LOCAL_IPADDR_PREFIX   In order to restict the access of remote users, 
#                          we must be able to identify local users.  This
#                          string contains the address prefix of your
#                          local IP addresses, for example '137.99.'.
# 
#    TEMPLATE_FILE   This configuration setting is optional.  The
#                    script uses an HTML template in which to imbed
#                    its HTML output.  This is the name of the template.
#                    Within this template, occurances of the string
#                    <!--TITLE--> is replaced by the web page title, and
#                    <!--REPLACE--> is replaced by the remaining HTML output.
#                    If this option is left blank or omitted, a simple
#                    default template is used.

import re
import os
import os.path
import string
import cgi
import sys
import time
import random
import urllib

#we need the IPv4 manipulation library from google
#http://code.google.com/p/ipaddr-py/
import ipaddr

#-----------------------------------------------------------------------
#  History
#-----------------------------------------------------------------------
#  2005-04-12 JR:  The DownloadForm() function would fail sometimes if
#                  an unknown file was requested.  Fix: place os.stat()
#                  call in a try/except clause.
#  2005-04-15 JR:  Amended function clean_filename() to convert 
#                  ampersands (&) to underscores (_), because when 
#                  ampersand is used in the file name it gets used
#                  in the URL, and when downloading the file the browser 
#                  interprets the & as a field separator and not a 
#                  character in the filename.
#  2005-04-18 JR:  Revert above change to clean_filename(), because the
#                  resulting renaming of the user's file (& -> _) might
#                  be confusing.  Instead, use urllib.quote() to quote
#                  links containing & and other troublesome charcters
#                  in the functions DownloadForm() and DownloadFile()
#                  
#  2009-03-09 RM:  hacking on this thing to support different IP address
#		   classes
#-----------------------------------------------------------------------
#  LOCAL CONFIGURATION
#-----------------------------------------------------------------------

#  Your location name
YOUR_LOCATION = "UConn School of Engineering"

# File size limit in MB
FILE_LIMIT=2048
#FILE_LIMIT=10240

# File retention length in days.
FILE_RETENTION=8

#  Drop box directory (make sure it's owned by web server user)
DROPBOX_BASE_DIR="/dropbox"

#  Local address
LOCAL_IPADDR_PREFIX="137.99."

#  Dropbox HTML template 
#  (optional, a default template - see DEFAULT_TEMPLATE below - 
#  is automatically provided if this file cannot be found or opened).
#  You can create this text file using the placeholders given above, and place it in the same directory as this script.
TEMPLATE_FILE="soe_template"


#-----------------------------------------------------------------------
#  Constants
#-----------------------------------------------------------------------

#  Number of characters in generated password
NPASSWD = 16

#  Set actual file limit to 6% larger than stated limit.
#  This accounts for 
#    * the discrepancy between the two kinds of MB,
#      10^6 and 2^20 (the later is 4.9% larger), and
#    * gives the user a 2% grace interval.
UPLOAD_SIZE_LIMIT = FILE_LIMIT * 1000000 * 1.069

#  Password characters
passwd_chars = "0123456789" + \
	"ABCDEFGHIJKLMNOPQRSTUVWXYZ" + \
	"abcdefghijklmnopqrstuvwxyz"

#  Size of buffer used to transfer files
BUFSIZE=65536

#  Name of upload field
UPLOAD_FIELD_NAME = "upload"

#  File location
DROPBOX_DIR  = DROPBOX_BASE_DIR + "/files"

#  Log location
LOGDIR       = DROPBOX_BASE_DIR + "/log"
LOGFILE      = LOGDIR + "/" + "dropbox.log"


#  Environmental constants
if os.environ.has_key("SCRIPT_NAME"):
	SCRIPT_NAME = os.environ["SCRIPT_NAME"]
else:
	SCRIPT_NAME = ""

if os.environ.has_key("SERVER_NAME"):
	SERVER_NAME = os.environ["SERVER_NAME"]
else:
	SERVER_NAME = ""

#  Add port to server name if needed
if os.environ.has_key("SERVER_PORT"):
	port=os.environ["SERVER_PORT"]
	if os.environ.has_key("HTTPS"):
		if not port=="443":
			SERVER_NAME = SERVER_NAME + ":" + port
	else:
		if not port=="80":
			SERVER_NAME = SERVER_NAME + ":" + port
			
#  Upload form HTML
UPLOAD_FORM = """
<br><br>
<form action='%s?upload=yes' enctype='multipart/form-data' method='post'>
<table cellpadding='8' cellspacing='8'>
<tr>
<td bgcolor='white'>
<b>
Step 1: Enter file name
</b>
</td>
<td bgcolor='#ffffff'>

<input class='form_textfield' type='file' name='%s' size='48'></td>
<td>
<font color='gray'>
<i>
</i>
</font>
</td>
</tr>
<tr>
<td bgcolor='white'>
<b>
Step 2: Push the button
</b>
</td>
<td bgcolor='#ffffff'>
<input class='form_button' type='submit' name='submit' value='Upload File'>
</td>
<td>
<font color='gray'>
<i>

</i>
</font>
</td>
</tr>
</table>
</form>
<br>
<br>
<div class='info'>
<h3><b>
This service provides large file sharing.
Before using, please read the following.
</b></h3>
<dl>
<br>
<dt>
<b>This service is for %s members only (either <i>sender and/or receiver</i>)</b>.
<dd>
This application is intended to be used by members of %s, both
within the community and in correspondence with individuals outside of %s.
<b><i>
Either the sender or receiver of the document must be within at the %s and have an @engr.uconn.edu address.  Please refer to <a href="http://www.ct.gov/doit/cwp/view.asp?a=1245&Q=314686">this page</a> for the policy regarding Acceptable Use.
</i></b>
<br><br>
<dt>
<b>The maximum file size is %s MB</b>.
<dd>
The maximum file size is %s MB.  This limit is enforced
<b><i>after</i></b> you upload your file.  
Your file will not be rejected until after your transfer completes.
<br><br>
<dt>
<b>Files are deleted after %s days</b>.
<dd>
Files uploaded to this server will be retained for only %s days.
This service is intended for file 
sharing, not for long term storage.
<br><br>
<dt>
<b>Save the link displayed after uploading</b>.
<dd>
After your file upload completes, you will be shown a link that can be
used to retrieve your file.  Cut and paste this link into your Email
client and send it to your intended recipient(s).
</dl>
</div>
""" % (
SCRIPT_NAME, 
UPLOAD_FIELD_NAME,
YOUR_LOCATION, YOUR_LOCATION, YOUR_LOCATION, YOUR_LOCATION, 
FILE_LIMIT, FILE_LIMIT, 
FILE_RETENTION, FILE_RETENTION)


#  Default web template.
#
#   This script replaces the following strings in the template,
#      --TITLE--     replace with the web page title.
#      --REPLACE--   replace with the dropbox upload form or other
#                    content.
#
DEFAULT_TEMPLATE = """
<html>
<head>
<style type="text/css">
body {
	color: black;
	background: white;
	margin: 0em;
	font-family: sans-serif;
}
.info {
	width: 40em;
}
</style>
<title>
<!--TITLE-->
</title>
</head>
</body>
<h2>
<!--TITLE-->
</h2>
<hr noshade>
<!--REPLACE-->
</body>
</html>
"""

#-----------------------------------------------------------------------
#  Functions
#-----------------------------------------------------------------------

#  Read HTML template, insert data, dispay and end program.
def display_page(title,msg):
	try:
		f = open(TEMPLATE_FILE)
		template = f.read()
		f.close()
	except:
		template = DEFAULT_TEMPLATE
	template = string.replace(template,'<!--TITLE-->', title)
	template = string.replace(template,"<!--REPLACE-->", msg)
	print "Content-type: text/html\n"
	print template
	#  End program here
	raise SystemExit

#  Display title and msg on templated web page
def display_error_page(msg):
	display_page("File Drop Box: ERROR", msg)


#  Generate random password
def gen_passwd(n,chars):
	random.seed(None)
	passwd = []
	for i in range(n):
		passwd.append(random.choice(chars))
	return string.join(passwd,'')


#  Gets basename from a Windows file name.
def clean_filename(file_name):
	
	#  If file uploaded from windows, then 
	#    we need to change backslash to forward slash and then get basename.
	file_name = os.path.basename(string.replace(file_name,'\\','/'))

	#  Unquote any special characters.  Most browsers seem not to send quoted
	#  characters, but some do and if we do not unquote them now the cause
	#  problems when it's time to download.
	file_name = urllib.unquote_plus(file_name)

	return file_name


#  Form local file name from original name and password.
def get_filepath(input_file_name,passwd):
	file_name, file_ext = os.path.splitext(input_file_name)
	return "%s/%s.%s%s" % (DROPBOX_DIR,file_name,passwd,file_ext)

#  Determine if address is local or remote
def is_addr_remote(remote_address):
	#  ip address starts with local prefix
        # rohit's ip hacks here
	if ipaddr.IPv4('137.99.0.0/20').__contains__(ipaddr.IPv4(remote_address)):
		return 0
	elif ipaddr.IPv4('67.221.64.0/255.255.224.0').__contains__(ipaddr.IPv4(remote_address)):
                return 0
	elif ipaddr.IPv4('137.99.240.0/255.255.252.0').__contains__(ipaddr.IPv4(remote_address)):
                return 0
	elif string.find(remote_address,"10.")==0:
		return 0
	else:
		return 1

#  Read GET data
def read_GET():
	#  Look for arguments in environment and argument string
	if os.environ.has_key("QUERY_STRING"):
		args = os.environ["QUERY_STRING"]
	elif len(sys.argv)>1:
		args = sys.argv[1]
	#  No arguments found
	else:
		return {}
	#  Parse arguments
	GET = {}
	for arg in string.split(args,"&"):
		fields = string.split(arg,"=")
		if len(fields)==2:
			GET[urllib.unquote_plus(fields[0])] = urllib.unquote_plus(fields[1])
	return GET


#  Read original file name and file data from multipart form on STDIN,
#  writ to file_name_prefix + filename
def parse_file(fin,dir_name,passwd,file_size_limit):
	clean_name = ""
	file_path  = ""
	file_size  = 0
	field      = ""
	filename   = ""
	nread      = 1
	nline      = 0
	fout       = 0

	#  Regular expression to extract field name and file name from header data
	fileheader = re.compile('Content-Disposition: form-data; name="([^"]+)"; filename="([^"]+)"',re.IGNORECASE)

	#  Get border, truncate \r\n
	border = fin.readline()[0:-2]

	#  read var information
	while nread:
		#  read header
		while nread:
			line = fin.readline()
			nread = len(line)
			nline = nline+1
			if not line:
				break
			res = fileheader.findall(line)
			#  Found file header
			if res:
				#  Pull field name and file name from header
				field,filename = res[0]
				#  Open output file
				clean_name = clean_filename(filename)
				file_path = get_filepath(clean_name,passwd)
				fout = open(file_path,"w")
			#  End of headers
			elif line=="\r\n" or line=="\n" or line=="\r":
				break

		#  read data until find border
		prev_suffix = ""
		while nread:
			line = fin.readline()
			nline = nline+1
			nread = len(line)
			if not line:
				break
			#  If border then end of section
			if string.find(line,border)!=-1:
				break
			#  Remove trailing \r and \n
			if line[-2:]=="\r\n":
				suffix = "\r\n"
				line = line[:-2]
			elif line[-1:]== "\n":
				suffix = "\n"
				line = line[:-1]
			if field:
				file_size = file_size + len(prev_suffix) + len(line)
				if file_size<=file_size_limit:
					fout.write(prev_suffix)
					fout.write(line)
			prev_suffix = suffix

		#  Close open file, turn off file indicator
		if fout:
			fout.close()
			fout = 0
			field = ""
			filename = ""

	return clean_name,file_path,file_size


#  Return web page title and content of upload form.
def BuildUploadForm():
	title = "File Upload"
	return title, UPLOAD_FORM 


#  Return web page title adn content of download form.
def DownloadForm(form,is_remote):
	title = "File Download"
	#  Get filename
	if form.has_key('n'):
		file_name = form['n']
	else:
		file_name = ""
	#  Get password
	if form.has_key('p'):
		passwd = form['p']
	else:
		passwd = ""
	#  Make link
	link  = "http://%s%s?d=1&n=%s&p=%s" % (SERVER_NAME,SCRIPT_NAME,urllib.quote(file_name),passwd)
	#  Get file size for display
	print "test: file_name (%s)<br>" % file_name
	try:
		file_path = get_filepath(file_name,passwd)
		filesize = int(os.stat(file_path)[6])
	except:
		write_log("download ERROR WRONG_NAME_OR_PASSWORD " + file_path)
		title = "Failure - Wrong file name or password"
		msg = "Sorry.  Either that file (<u><b>%s</b></u>) does not exist or you've sent the wrong password." % file_name
		return title,msg
	if filesize>=1000000:
		filesize = "%.1f MB" % (filesize/1000000.)
	else:
		filesize = "%.1f KB" % (filesize/1000.)
	#  Print link
	msg = """
		<br><br><br>
		<p align="center">
		<i>
		<b>Right click</b> (or <b>Control click</b> for Mac users) 
		on the following link to download your file.
		</i>
		</p>
		<br><br>
		<p align="center">
		<a href="%s">%s</a> &nbsp; (%s)
		</p>
	""" % (link,file_name,filesize)
	return title,msg


#  Receive file uploaded by user in response to Upload Form.
def UploadFile(is_remote):
	#  Generate random password
	#     If passwd starts with L, the file is Locally readable only.
	#     If passwd starts with W, the file is World   readable.
	if is_remote:
		passwd = 'L'
	else:
		passwd = 'W'
	passwd = passwd + gen_passwd(NPASSWD,passwd_chars)
	#  Read file from stdin and store in DROPBOX_DIR.
	filename, filepath, upload_size = parse_file(sys.stdin,DROPBOX_DIR,passwd,UPLOAD_SIZE_LIMIT)
	#  If no upload size, give error
	if upload_size==0:
		if filepath:
			os.unlink(filepath)
		title = "File Upload Failure"
		msg = "<b>ERROR</b>: The file you attempted to upload ('<b>%s</b>') is empty or does not exist." % filename
		write_log("upload ERROR EMPTY_FILE %s" % filename)
		return title,msg
	#  If file too big, give error
	if upload_size > UPLOAD_SIZE_LIMIT:
		if filepath:
			os.unlink(filepath)
		title = "File Too Big"
		msg = "<b>ERROR</b>: Your file (<b>%s</b>) has a size of <b>%s</b> bytes, and exceeds the <b>%s MB</b> limit." % (
			filename, upload_size, FILE_LIMIT)
		write_log("upload ERROR FILE_TOO_BIG %s %s %d" % (filename,upload_size,UPLOAD_SIZE_LIMIT))
		return title,msg
	#  Show user link to download page
	link  = "http://%s%s?n=%s&p=%s" % (SERVER_NAME,SCRIPT_NAME,urllib.quote(filename),passwd)
	title = "File Upload Successful (%s)" % filename
	msg = """
<br><br>
Please send the following link to your intended recipient(s).
<br><br>
<a href="%s">%s</a>
""" % (link,link)
	write_log("upload SUCCESS %s %s" % (filename,upload_size))
	return title,msg


#  Download file to user.
def DownloadFile(form,is_remote):
	#  Get filename
	file_name=form['n']
	#  Get password
	if form.has_key('p'):
		passwd = form['p']
	else:
		passwd = ""
	file_path = get_filepath(file_name,passwd)
	#  Do not allow download if user is remote and 'passwd' starts with
	#  'L' (which means Locally readable only)
	if is_remote and passwd[0]=='L':
		title = "Failure - Access Denied"
		msg = "<br>Sorry, you've requested a file which is only readable by SoE users."
		write_log("download ERROR ON_CAMPUS_ONLY " + file_path)
		return title,msg
	#  Retreive file
	else:
		#  Wrong file name or password.
		if not os.path.isfile(file_path):
			write_log("download ERROR WRONG_NAME_OR_PASSWORD " + file_path)
			title = "Failure - Wrong file name or password"
			msg = "Sorry.  Either that file (<u><b>%s</b></u>) does not exist or you've sent the wrong password." % file_name
			return title,msg
		#  Actual file download
		else:
			write_log("download SUCCESS " + file_path)
			print "Content-Disposition: attachment; filename=\"%s\"" % file_name
			print "Content-Type: application/octet-stream\n"
			#  Write file
			fin = open(file_path,"r")
			while 1:
				buffer = fin.read(BUFSIZE)
				if not buffer:
					break
				sys.stdout.write(buffer)
			fin.close()
			# end cgi program now (to close file transfer to browser)
			sys.exit()
	

#  Write add site entry into log file
def write_log (msg):
	#  Get date
	timelocal = time.localtime(time.time())
	date = time.strftime("%Y-%m-%d %H:%M:%S", timelocal)
	#  Get ipaddr if present
	if os.environ.has_key("REMOTE_ADDR"):
		ipaddr = os.environ["REMOTE_ADDR"]
	else:
		ipaddr = "-"
	#  Create log directory if it doesn't exist
	if not os.path.isdir(LOGDIR):
		os.mkdir(LOGDIR)
	#  Append date, ipaddr, msg to logfile.
	f = open(LOGFILE, "a")
	f.write("%s %s %s\n" % (date, ipaddr, msg))
	f.close()



#-----------------------------------------------------------------------
#  Main routine
#-----------------------------------------------------------------------

#DEBUG
#sys.stderr = sys.stdout
#print "Content-type: text/html\n"

#  Can't find client's IP address.
if not os.environ.has_key("REMOTE_ADDR"):
	title = "ERROR"
	msg = "<b>ERROR</b>:  I cannot determine the IP address of your computer."
	display_page(title,msg)

#  Is user local or remote?
is_remote = is_addr_remote(os.environ["REMOTE_ADDR"])

#  Make sure tmp directory exists
DROPBOX_TMP_DIR = DROPBOX_DIR + "/" + "tmp"
if not os.path.isdir(DROPBOX_TMP_DIR):
	os.mkdir(DROPBOX_TMP_DIR)

#  Look for GET data
GET = read_GET()

#  Download if 'd' (file name) field present.
if GET.has_key('d'):
	title,msg = DownloadFile(GET,is_remote)

#  Show download page if no 'd'.
elif GET.has_key('n'):
	title,msg = DownloadForm(GET,is_remote)

#  Upload file if present
elif GET.has_key('upload'):
	title, msg = UploadFile(is_remote)

#  Build upload form
else:
	title,msg = BuildUploadForm()

#  Display page (proram execution ends within this function)
display_page(title,msg)
