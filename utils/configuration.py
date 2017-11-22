from utils.singleton import singleton
from utils import common
from config import constant
import os

@singleton
class Kconfig():
	def __init__(self):
		pass

	def init(self):
		self.debug = constant.DEBUG

		if self.debug:
			self.server = constant.DEBUG_SERVERPORT
			self.server_publickey = "DEBUG"
			self.client_publickey = constant.DEBUG_PUBLIC_KEY
			self.client_privatekey = constant.DEBUG_PRIVATE_KEY
			self.credential = constant.DEBUG_CREDENTIAL
		else:
			self.server_url = constant.SERVER_URL
			
			self.server_publickey = self.read_server_publickey()
			self.client_publickey = self.read_client_publickey()
			self.client_privatekey = self.read_client_privatekey()
			self.credential = self.read_credential().strip()
			
		self.log_path = constant.LOG_FILE
		self.log_max_bytes = constant.LOG_MAX_BYTES
		self.log_backup_count = constant.LOG_BACKUP_COUNT
		
		if not self.server_publickey:
			print("No server publickey file exists")
			return False
			
		if not self.client_publickey:
			print("No client public key exists")
			return False
			
		if not self.client_privatekey:
			print("No client private key exists")
			return False
			
		if not self.credential:
			print("No credential file exists")
			return False
			
		return True
		
	def read_server_publickey(self):
		return common.cat(os.path.join(common.get_work_dir(), constant.SERVER_PUBLIC_KEY))
		
	def read_client_publickey(self):
		return common.cat(os.path.join(common.get_work_dir(), constant.RSA_PUBLIC_KEY))
		
	def read_client_privatekey(self):
		return common.cat(os.path.join(common.get_work_dir(), constant.RSA_PRIVATE_KEY))
		
	def read_credential(self):
		return common.cat(os.path.join(common.get_work_dir(), constant.CREDENTIAL))