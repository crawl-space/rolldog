# Rolldog

[![Deploy](https://www.herokucdn.com/deploy/button.png)](https://heroku.com/deploy?template=https://github.com/jbowes/rolldog)

Rolldog is a webhook service to translate [Rollbar](https://rollbar.com) items into [Datadog](https://www.datadoghq.com/) events.

It includes optional [Slack](https://slack.com/) integration as well, if you don't want to grant read permission to all your channels to Rollbar.

## Setup

1. Deploy Rolldog to Heroku (or elsewhere).
2. Configure the following for Rolldog:
  - `ROLLBAR_URL` (optional) The url of your project in Rollbar (ex: https://rollbar.com/RadCompany/AwesomeProduct/items/)
  - `ROLLDOG_TOKEN` A secret token that you'll use to setup the Rollbar outgoing webhook.
  - `DATADOG_API_KEY` One of your Datadog [API keys](https://app.datadoghq.com/account/settings#api).
  - `DATADOG_ENV_PREFIX` (optional) A value to prefix environment tags with, (ex: `inventory`).
  - `SLACK_HOOK_URL` (optional) An incoming webhook URL for Slack. Make sure to pick an appropriate channel, a cool name, and set a nice avatar!
3. Add a new webhook notification in Rollbar. Use the url of your heroku deploy, and include `?token=WHATEVER_YOU_SET_FOR_ROLLDOG_TOKEN`.

## Screenshots

![](http://i.imgur.com/uE1dDxJ.png)
![](http://i.imgur.com/DafFj6e.png)
