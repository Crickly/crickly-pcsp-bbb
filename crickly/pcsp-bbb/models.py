# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models

from crickly.core import models as coremodels


class Ball(models.Model):
    # Ball identifiers
    ball_key = models.CharField(max_length=8)
    match = models.ForeignKey(
        coremodels.Match,
        on_delete=models.CASCADE,
        related_name='match'
    )
    innings_number = models.IntegerField()
    over_number = models.IntegerField()
    ball_number = models.IntegerField()

    # Players Involved
    batsman = models.ForeignKey(
        coremodels.Player,
        on_delete=models.CASCADE,
        related_name='batsman'
    )
    non_striker = models.ForeignKey(
        coremodels.Player,
        on_delete=models.CASCADE,
        related_name='non_striker'
    )
    bowler = models.ForeignKey(
        coremodels.Player,
        on_delete=models.CASCADE,
        related_name='bowler'
    )
    fielder = models.ForeignKey(
        coremodels.Player,
        on_delete=models.CASCADE,
        related_name='fielder'
    )

    # Runs scored
    runs = models.IntegerField()
    bat_runs = models.IntegerField()
    extra_runs = models.IntegerField()
    wides = models.IntegerField()
    noballs = models.IntegerField()
    byes = models.IntegerField()
    leg_byes = models.IntegerField()

    # Wickets
    is_wicket = models.BooleanField()
    out_batsman = models.ForeignKey(
        coremodels.Player,
        on_delete=models.CASCADE,
        related_name='out_batsman'
    )
    how_out = models.IntegerField()

    # Totals
    total_balls = models.IntegerField()
    total_bowler_balls = models.IntegerField()
    total_batsman_balls = models.IntegerField()

    total_runs = models.IntegerField()
    total_bat_runs = models.IntegerField()
    total_extra_runs = models.IntegerField()

    total_wickets = models.IntegerField()
    total_bowler_wickets = models.IntegerField()

    # Wagon wheel
    wagon_x = models.FloatField()
    wagon_y = models.FloatField()
