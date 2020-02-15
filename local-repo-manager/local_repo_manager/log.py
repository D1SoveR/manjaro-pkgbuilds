from datetime import datetime
import os.path
import sys

class LogToFile:

	__slots__ = ("fp", "log_directory")

	def __init__(self, log_directory):
		self.log_directory = log_directory

	def __enter__(self):
		current_time = datetime.now()
		log_filename = "build-{0:%Y-%m-%dT%H-%M-%S}.log".format(current_time)
		self.fp = open(os.path.join(self.log_directory, log_filename), mode="wb")
		self.fp.write("BUILD LOG FOR {0:%d %B %Y at %H:%M}\n================================\n\n".format(current_time).encode())
		self.fp.flush()
		return (self.fp, log_filename)

	def __exit__(self, *args):
		self.fp.close()
		del self.fp
		del self.log_directory

class LogToStdout:
	def __enter__(self):
		return (sys.stdout, "terminal")
	def __exit__(self, *args):
		pass