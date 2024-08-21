import os, random, string, requests, upnpclient, socket
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for, flash
from flask_cors import CORS, cross_origin

app = Flask(__name__)
CORS(app)

app.config.from_pyfile('config.py')
app.secret_key = app.config['SECRET_KEY']

def get_local_ip():
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	s.settimeout(0)
	try:
		s.connect(('8.8.8.8', 1))
		local_ip = s.getsockname()[0]
	except Exception:
		local_ip = '127.0.0.1'
	finally:
		s.close()

	print(f'Local IP: {local_ip}')
	
	return local_ip

def setup_upnp():
	local_ip = get_local_ip()

	try:
		devices = upnpclient.discover()

		if not devices:
			print('No UPnP devices found.')
			return

		d = None
		for device in devices:
			for service in device.services:
				if 'WANIPConn' in service.service_id or 'WANPPPConn' in service.service_id:
					d = device
					break
			if d:
				break

		if not d:
			print('No router found.')
			return
		
		print(f'Using UPnP device: {d.friendly_name}')

		d.WANIPConn1.AddPortMapping(
			NewRemoteHost='0.0.0.0',
			NewExternalPort=5000,
			NewProtocol='TCP',
			NewInternalPort=5000,
			NewInternalClient=local_ip,
			NewEnabled='1',
			NewPortMappingDescription='Flex Server',
			NewLeaseDuration=10000
		)
		print(f'Port 5000 mapped successfully.')
	except Exception as e:
		print(f'Failed to set up port forwarding: {str(e)}')

@app.route('/')
def index():
	return render_template('index.html')

@app.route('/account-link', methods=['GET', 'POST'])
@cross_origin()
def account_link():
	if request.method == 'POST':
		username = request.form['username']

		link_code = ''.join(random.choices(string.ascii_lowercase + string.ascii_uppercase + string.digits, k=32))

		try:
			server_ip = requests.get('https://api.ipify.org').text
		except Exception as e:
			flash(f'Failed to get server ip: {str(e)}')
			return redirect(url_for('account_link'))
		
		data = {
			'username': username,
			'server_ip': server_ip,
			'link_code': link_code
		}

		try:
			response = requests.post('http://localhost:4000/server-link-init', json=data)

			if response.status_code == 200:
				flash(f'Linking code generated: {link_code}')
			else:
				flash(f'Failed to send data to the client: {response.text}')
		except Exception as e:
			flash(f'Error sending data to the client: {str(e)}')

		return redirect(url_for('account_link'))
	
	return render_template('account_link.html')

@app.route('/change-folder', methods=['GET', 'POST'])
def change_folder():
	message = ''

	if request.method == 'POST':
		folder_path = request.form.get('folder_path')
		if folder_path and os.path.isdir(folder_path):
			app.config['UPLOAD_FOLDER'] = folder_path
			message = f'Folder path updated to: {folder_path}'
		else:
			message = 'Invalid path. Please enter a valid folder path.'

	return render_template('change_folder.html', message=message)

@app.route('/files', methods=['GET'])
def list_dirs():
	try:
		file_list = []
		for root, dirs, files in os.walk(app.config['UPLOAD_FOLDER']):
			for file in files:
				ext = file.split('.')
				if ext[-1] == 'mp4':
					relative_path = os.path.relpath(os.path.join(root, file), app.config['UPLOAD_FOLDER'])
					file_list.append(relative_path)
		return jsonify(file_list)
	except Exception as e:
		return jsonify({"msg": "Could not list files", "error": str(e)}), 500
	
@app.route('/files/<path:filename>', methods=['GET'])
@cross_origin()
def serve_file(filename):
	try:
		return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
	except Exception as e:
		return jsonify({"msg": "File not found", "error": str(e)}), 404

if __name__ == '__main__':
	setup_upnp()
	app.run(host='0.0.0.0', port=5000)