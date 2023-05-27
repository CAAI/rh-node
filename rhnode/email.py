import os
import smtplib
from email.message import EmailMessage

# os.environ["RHNODE_EMAIL_ON_ERROR"] Testing purposes only


class EmailSender(object):
    def __init__(self):
        super().__init__()
        self.email_to = os.environ["RHNODE_EMAIL_ON_ERROR"]
        self.email_from = "rhnode@regionh.dk"

    def send_email_exception(self, node_name, host_name, datetime):
        email = EmailMessage()
        email.set_content(
            f"""
                Exception on production server: {host_name}, 
                node {node_name}. Timestamp: {datetime}
            """
        )
        email["Subject"] = f"Prod. error: {host_name}: {node_name}, {datetime}"
        email["To"] = self.email_to
        email["From"] = self.email_from
        try:
            with smtplib.SMTP("10.140.209.2", 25) as server:
                server.ehlo()
                server.sendmail(self.email_from, self.email_to, email.as_string())
        except Exception as e:
            print(e)


import datetime

EmailSender().send_email_exception("test_node", "test_host", datetime.datetime.now())
