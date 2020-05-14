Crickly-pcsp-bbb 🏏
==================================

Crickly-PCSP-BBB is an extension to [Crickly](https://github.com/Crickly/Crickly/). It adds support for ball by ball from Play-Cricket Scorer Pro. This extension also requires the [Crickly-PlayCricket](https://github.com/crickly/crickly-playcricket) extension.

📝 _Note_: Development is still in progress and not in a stable state. I doubt it'll (know it wont) work yet! 🤪

Detailed documentation is in the "docs" directory. (Not produced yet. So instead heres a unicorn... 🦄)


Quick start 🛫
-------------


1. Ensure you have `crickly.core` and `crickly.playcricket` in your `INSTALLED_APPS`

2. Add `crickly.pcsp_bbb` to your `INSTALLED_APPS` 

```
    INSTALLED_APPS = [
        ...
        'crickly.core',
        'crickly.playcricket',
        'crickly.pcsp_bbb',
        ...
    ]
```

2. Run `python manage.py migrate` to create the crickly models.
