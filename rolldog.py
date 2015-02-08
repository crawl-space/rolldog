import json
import logging
import os
import sys

from datetime import datetime

import falcon
import requests

log = logging.getLogger("rolldog")

ROLLBAR_URL = os.environ.get("ROLLBAR_URL")
ROLLDOG_TOKEN = os.environ.get("ROLLDOG_TOKEN")
DATADOG_API_KEY = os.environ.get("DATADOG_API_KEY")

SLACK_HOOK_URL = os.environ.get("SLACK_HOOK_URL")


def pp_date(timestamp):
    return datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


class CheckToken(object):

    def process_request(self, req, resp):
        token = req.get_param("token", required=True)
        if token != ROLLDOG_TOKEN:
            raise falcon.HTTPUnauthorized("Invalid token",
                    "Make sure 'token' is correct.")


class RequireJSON(object):

    def process_request(self, req, resp):
        if req.method == "POST":
            if "application/json" not in req.content_type:
                raise falcon.HTTPUnsupportedMediaType(
                    "This API only supports requests encoded as JSON.")


class ResponseLoggerMiddleware(object):

    def process_response(self, req, resp, resource):
        log.info('{0} {1} {2}'.format(req.method, req.relative_uri,
            resp.status[:3]))


class RollbarResource:

    def on_post(self, req, resp):
        item = json.load(req.stream)

        try:
            # self.send_to_datadog(item)
            self.send_to_slack(item)
        except:
            log.exception("Failed to send!")
            raise falcon.HTTPBadGateway("Error sending data",
                    "Could not reach upstream")

        resp = falcon.HTTP_204

    def send_to_datadog(self, item):
        text = notification.description + "\n"
        text += "\n".join(["{} - {}".format(app.name, app.description)
            for app in notification.apps])

        payload = {
            "title": notification.title,
            "text": text,
            "tags": ["rollbar"],
            "alert_type": "warning" if notification.errored else "info",
            }

        r = requests.post(url + "?api_key=" + DATADOG_API_KEY,
                data=json.dumps(payload))
        r.raise_for_status()

    def send_to_slack(self, item):
        if not SLACK_HOOK_URL:
            return

        default_color = "#3399FF"
        event_name = item["event_name"]

        if event_name == "new_item":
            pretext = "New item"
            color = "danger"
        elif event_name == "reactivated_item":
            pretext = "Reactivated item"
            color = "danger"
        elif event_name == "resolved_item":
            pretext = "Resolved item"
            color = "good"
        elif event_name == "exp_repeat_item":
            pretext = "Resolved item"
            color = "warning"
        elif event_name == "reopened_item":
            pretext = "Reopened item"
            color = default_color
        elif event_name == "deploy":
            pretext = "Deploy"
            color = default_color
        else:
            raise Exception("Unknown event type: %s" % event_name)

        title_link = None

        if event_name == "deploy":
            payload = item["data"]["deploy"]
            title = payload["comment"]
        else:
            payload = item["data"]["item"]
            title = "#{} {}".format(payload["counter"], payload["title"])
            if ROLLBAR_URL:
                title_link = ROLLBAR_URL + str(payload["counter"])

        fallback = "{}: {}".format(pretext, title)

        fields = []

        if "first_occurrence_timestamp" in payload:
            fields.append({
                "title": "First Seen",
                "value": pp_date(payload["first_occurrence_timestamp"]),
                "short": True,
                })
            fields.append({
                "title": "Last Seen",
                "value": pp_date(payload["last_occurrence_timestamp"]),
                "short": True,
                })

        if "total_occurrences" in payload:
            fields.append({
                "title": "Occurences",
                "value": payload["total_occurrences"],
                "short": True,
                })

        if "revision" in payload:
            fields.append({
                "title": "Revision",
                "value": payload["revision"],
                "short": True,
                })

        fields.append({
            "title": "Environment",
            "value": payload["environment"],
            "short": True
            })


        msg = {
            "attachments": [{
                "pretext": pretext,
                "fallback": fallback,
                "title": title,
                "title_link": title_link,
                "color": color,
                "fields": fields,
                }]
            }

        r = requests.post(SLACK_HOOK_URL, data=json.dumps(msg))
        r.raise_for_status()


def configure():
    if not ROLLBAR_URL:
        log.error("ROLLBAR_URL is not set. no links will be configured")
    if not ROLLDOG_TOKEN:
        log.error("Please set ROLLDOG_TOKEN")
        sys.exit(-1)
    if not DATADOG_API_KEY:
        log.error("Please set DATADOG_API_KEY")
        sys.exit(-1)
    if not SLACK_HOOK_URL:
        log.error("SLACK_HOOK_URL not set. Slack integration is disabled")


logging.basicConfig()
log.setLevel(logging.INFO)

configure()

app = falcon.API(middleware=[
    CheckToken(),
    RequireJSON(),
    ResponseLoggerMiddleware(),
    ])
app.add_route("/", RollbarResource())
