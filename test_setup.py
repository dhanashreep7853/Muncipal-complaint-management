from google import genai
from dotenv import load_dotenv
import os

from flask import Flask, jsonify, render_template, request, redirect, session, url_for, flash
import sqlite3
from datetime import datetime, timedelta
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
# import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# from dotenv import load_dotenv
import json
import tempfile

print("✅ Libraries imported successfully!")