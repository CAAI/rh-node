import smtplib
from email.message import EmailMessage
from datetime import timedelta


class EmailSender(object):
    def __init__(self, recipient):
        super().__init__()
        self.email_to = recipient
        self.email_from = "rhnode@regionh.dk"

    def send_email_exception(self, node_name, host_name, datetime):
        email = EmailMessage()

        # datetime minus 2 minutes
        datetime_minus_2 = (datetime - timedelta(minutes=2)).isoformat()

        email.set_content(
            f"""
                Exception on production server: {host_name}, 
                node {node_name}. Timestamp: {datetime}

                To see the logs leading up to this error, run the following commands:

                ssh rhnode@{host_name}
                docker logs [folder]-{node_name} --since {datetime_minus_2} --timestamps
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
