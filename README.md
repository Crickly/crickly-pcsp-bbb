Crickly-pcsp-bbb 🏏
==================================

Crickly-PCSP-BBB is an extension to [Crickly](https://github.com/Crickly/Crickly/). It adds support for ball by ball from Play-Cricket Scorer Pro. This extension also requires the [Crickly-PlayCricket-Link](https://github.com/crickly/crickly-playcricket-link) extension.

📝 _Note_: Development is still in progress and not in a stable state. I doubt it'll (know it wont) work yet! 🤪

Detailed documentation is in the "docs" directory. (Not produced yet. So instead heres a unicorn... 🦄)


Quick start 🛫
-------------
To use this app you will need an API Token provided by the [Play Cricket Helpdesk](https://play-cricket.ecb.co.uk/hc/en-us/requests/new?ticket_form_id=217809).


1. Add `crickly.core`, `crickly.playcricket` and `crickly.pcsp_bbb` to your INSTALLED_APPS setting like this

```
    INSTALLED_APPS = [
        ...
        'crickly.core',
        'crickly.playcricket',
        'crickly.pcsp_bbb',
    ]
```

2. Run `python manage.py migrate` to create the cricket models.
