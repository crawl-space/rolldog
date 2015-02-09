# coding=utf-8

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
DATADOG_ENV_PREFIX = os.environ.get("DATADOG_ENV_PREFIX", "")

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


class Event(object):

    def __init__(self, data):
        event_name = data["event_name"]

        self.is_deploy = False
        if event_name == "new_item":
            self.pretext = "New item"
            self.level = "error"
        elif event_name == "reactivated_item":
            self.pretext = "Reactivated item"
            self.level = "error"
        elif event_name == "resolved_item":
            self.pretext = "Resolved item"
            self.level = "good"
        elif event_name == "exp_repeat_item":
            self.pretext = "Resolved item"
            self.level = "warning"
        elif event_name == "reopened_item":
            self.pretext = "Reopened item"
            self.level = "warning"
        elif event_name == "deploy":
            self.is_deploy = True
            self.pretext = "Deploy"
            self.level = "info"
        else:
            raise Exception("Unknown event type: %s" % event_name)

        if self.is_deploy:
            self.payload = data["data"]["deploy"]
            self.title = self.payload["comment"]
        else:
            self.payload = data["data"]["item"]
            self.title = "#{} {}".format(self.payload["counter"],
                    self.payload["title"])

        self.fallback = "{}: {}".format(self.pretext, self.title)


class RollbarResource:

    def on_post(self, req, resp):
        item = json.load(req.stream)

        try:
            event = Event(item)
            self.send_to_datadog(event)
            self.send_to_slack(event)
        except:
            log.exception("Failed to send!")
            raise falcon.HTTPBadGateway("Error sending data",
                    "Could not reach upstream")

        resp = falcon.HTTP_204

    def send_to_datadog(self, event):
        alert_map = {
                "error": "error",
                "warning": "warning",
                "good": "success",
                "info": "info",
                }


        text = ""
        aggregation_key = None
        if not event.is_deploy:
            aggregation_key = "rollbar:" + str(event.payload["counter"])
            if ROLLBAR_URL:
                text = "{}{}".format(ROLLBAR_URL, event.payload["counter"])

        tags = ["rollbar", "{}:{}".format(DATADOG_ENV_PREFIX,
            event.payload["environment"])]

        # Datadog limits titles to 100 chars
        title = event.fallback
        if len(title) > 100:
            text = u"…" + title[99:] + "\n" + text
            title = title[:99] + u"…"

        msg = {
            "title": title,
            "text": text,
            "tags": tags,
            "aggregation_key": aggregation_key,
            "alert_type": alert_map[event.level],
            }

        datadog_url = "https://app.datadoghq.com/api/v1/events"
        r = requests.post(datadog_url + "?api_key=" + DATADOG_API_KEY,
                data=json.dumps(msg))
        r.raise_for_status()

    def send_to_slack(self, event):
        if not SLACK_HOOK_URL:
            return

        color_map = {
            "error": "danger",
            "warning": "warning",
            "good": "good",
            "info": "#3399FF",
            }

        title_link = None
        if not event.is_deploy and ROLLBAR_URL:
            title_link = ROLLBAR_URL + str(event.payload["counter"])

        payload = event.payload
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
                "pretext": event.pretext,
                "fallback": event.fallback,
                "title": event.title,
                "title_link": title_link,
                "color": color_map[event.level],
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
