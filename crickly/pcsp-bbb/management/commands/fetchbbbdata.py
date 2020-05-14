# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from django.conf import settings
from crickly.core import models as coremodels
from crickly.playcricket import models as pcmodels
from queue import Queue
from threading import Thread
from datetime import date, timedelta
import requests
import json


class Command(BaseCommand):
    help = 'will attempt to fetch the results data for matches with full_scorecard=False'
    API_URL = 'http://www.play-cricket.com/api/v2/'
    queue = Queue(maxsize=0)
    no_basic_uploads = 0
    no_full_uploads = 0
    no_innings_uploads = 0
    no_player_uploads = 0
    no_performance_uploads = 0
    no_not_uploaded = 0

    def get_data(self, url):
        r = requests.get(
            self.API_URL + url + '&api_token={}'.format(settings.PC_API_KEY)
        )
        if r.ok:
            return json.loads(r.content)
        else:
            r.raise_for_status()

    def is_innings_basic_data(self, innings):
        return len(innings['bat']) == 0 or len(innings['bowl']) == 0

    # def getParScores(self, no_batsmen, match_score):
    #     average_match_total = 0
    #     average_scores = {}
    #     for i in range(1, no_batsmen + 1):
    #         average_scores[i] = BattingParScores.objects.filter(bat_position=i)[0].average_score
    #         average_match_total += average_scores[i]
    #     parScores = {}
    #     for i in range(1, no_batsmen + 1):
    #         parScores[i] = (average_scores[i] / average_match_total) * match_score
    #     return parScores

    def zero_if_empty(self, value):
        return value if value != '' else 0

    def update_inning(self, match, inning, saved_inning, complete, match_data):
        if match_data['home_team_id'] == inning['team_batting_id']:
            bowl_team_id = match_data['away_team_id']
        else:
            bowl_team_id = match_data['home_team_id']

        bat_team = pcmodels.Team.objects.filter(
            pc_id=inning['team_batting_id']
        )[0].link
        bowl_team = pcmodels.Team.objects.filter(
            pc_id=bowl_team_id
        )[0].link
        saved_inning.bat_team_id = bat_team.id
        saved_inning.bowl_team_id = bowl_team.id
        saved_inning.runs = self.zero_if_empty(inning['runs'])
        saved_inning.wickets = self.zero_if_empty(inning['wickets'])
        saved_inning.overs = self.zero_if_empty(inning['overs'])
        saved_inning.declared = inning['declared']
        saved_inning.extras_byes = self.zero_if_empty(inning['extra_byes'])
        saved_inning.extras_leg_byes = self.zero_if_empty(inning['extra_leg_byes'])
        saved_inning.extras_wides = self.zero_if_empty(inning['extra_wides'])
        saved_inning.extras_no_balls = self.zero_if_empty(inning['extra_no_balls'])
        saved_inning.extras_penalties = self.zero_if_empty(inning['extra_penalty_runs'])
        saved_inning.extras_total = self.zero_if_empty(inning['total_extras'])
        saved_inning.complete_innings = complete
        saved_inning.save()

    def process(self, item):
        try:
            num_bat_unsures = 1
            num_bowl_unsures = 1
            pc_match = item[0]
            match = pc_match.link
            match_data = self.get_data(
                'match_detail.json?match_id={}'.format(pc_match.pc_id)
            )['match_details'][0]
            if pc_match.pc_id == str(match_data['id']):
                # check for innings in match data
                if match_data['result'] not in ['A', 'C', 'CON']:
                    try:
                        basic_info = self.is_innings_basic_data(
                            match_data['innings'][0]
                        ) or self.is_innings_basic_data(match_data['innings'][1])
                    except IndexError:
                        basic_info = True
                    if basic_info and not match.is_live_score():
                        # upload basic info
                        inning_no = coremodels.Inning.objects.filter(match__id=match.id).count()
                        if inning_no == 2:
                            pass  # ############################ TODO
                        elif inning_no == 0:
                            for i in match_data['innings']:

                                if match_data['home_team_id'] == i['team_batting_id']:
                                    bowl_team_id = match_data['away_team_id']
                                else:
                                    bowl_team_id = match_data['home_team_id']

                                bat_team = pcmodels.Team.objects.filter(
                                    pc_id=i['team_batting_id']
                                )[0].link
                                bowl_team = pcmodels.Team.objects.filter(
                                    pc_id=bowl_team_id
                                )[0].link

                                inningargs = {
                                    'runs': i['runs'] if i['runs'] != '' else 0,
                                    'wickets': i['wickets'] if i['wickets'] != '' else 0,
                                    'overs': i['overs'] if i['overs'] != '' else 0,
                                    'declared': i['declared'],
                                    'inning_no': 1 if i[
                                        'team_batting_id'
                                    ] == match_data['batted_first'] else 2,
                                }
                                inning = coremodels.Inning(**inningargs)
                                inning.match_id = match.id
                                inning.bat_team_id = bat_team.id
                                inning.bowl_team_id = bowl_team.id
                                inning.save()
                                self.no_innings_uploads += 1
                        elif inning_no == 1:
                            pass  # ######################## TODO

                        self.no_basic_uploads += 1
                        if match.date.get_date() < date.today() - timedelta(days=14):
                            match.processing_issue = True
                    else:
                        # full results upload
                        # check if two basic innings exist
                        saved_innings = coremodels.Inning.objects.filter(match__id=match.id)
                        if saved_innings.count() == 2:
                            # two innings exist so add to innings
                            for i in match_data['innings']:
                                inning = None
                                for saved_inning in saved_innings:
                                    # print('{} != {}, {}'.format(
                                    #     saved_inning.bat_team.id,
                                    #     pcmodels.Team.objects.filter(
                                    #         pc_id=i['team_batting_id']
                                    #     )[0].link.id,
                                    #     i['team_batting_id']
                                    # ))
                                    if saved_inning.bat_team.id == \
                                            pcmodels.Team.objects.filter(
                                                pc_id=i['team_batting_id'])[0].link.id:
                                        inning = saved_inning
                                        break
                                if inning is None:
                                    raise Exception('{} != {}'.format(
                                        saved_inning.bat_team.id,
                                        pcmodels.Team.objects.filter(
                                            pc_id=i['team_batting_id']
                                        )[0].link.id
                                    ))
                                # Check importance of complete_innings=True TODO
                                self.update_inning(match, i, inning, True, match_data)

                        elif saved_innings.count() == 1:
                            # Work out which inning exists and update it.
                            # Then add new inning (if exists).
                            saved_inning = saved_innings[0]
                            if len(match_data['innings']) == 1:
                                self.update_inning(
                                    match,
                                    match_data['innings'][0],
                                    saved_inning,
                                    True,
                                    match_data
                                )
                            elif len(match_data['innings']) == 2:
                                if match_data['innings'][0][
                                        'team_batting_id'
                                ] == saved_inning.bat_team_id:
                                    self.update_inning(
                                        match,
                                        match_data['innings'][0],
                                        saved_inning,
                                        True,
                                        match_data
                                    )
                                    unsaved_inning = match_data['innings'][1]
                                else:
                                    self.update_inning(
                                        match,
                                        match_data['innings'][1],
                                        saved_inning,
                                        True,
                                        match_data
                                    )
                                    unsaved_inning = match_data['innings'][0]

                                if match_data['home_team_id'] == i['team_batting_id']:
                                    bowl_team_id = match_data['away_team_id']
                                else:
                                    bowl_team_id = match_data['home_team_id']

                                bat_team = pcmodels.Team.objects.filter(
                                    pc_id=i['team_batting_id']
                                )[0].link
                                bowl_team = pcmodels.Team.objects.filter(
                                    pc_id=bowl_team_id
                                )[0].link

                                # Save unsaved inning.
                                inningargs = {
                                    'runs': self.zero_if_empty(
                                        unsaved_inning['runs']
                                    ),
                                    'wickets': self.zero_if_empty(
                                        unsaved_inning['wickets']
                                    ),
                                    'overs': self.zero_if_empty(
                                        unsaved_inning['overs']
                                    ),
                                    'declared': unsaved_inning['declared'],
                                    'extras_byes': self.zero_if_empty(
                                        unsaved_inning['extra_byes']
                                    ),
                                    'extras_leg_byes': self.zero_if_empty(
                                        unsaved_inning['extra_leg_byes']
                                    ),
                                    'extras_wides': self.zero_if_empty(
                                        unsaved_inning['extra_wides']
                                    ),
                                    'extras_no_balls': self.zero_if_empty(
                                        unsaved_inning['extra_no_balls']
                                    ),
                                    'extras_penalties': self.zero_if_empty(
                                        unsaved_inning['extra_penalty_runs']
                                    ),
                                    'extras_total': self.zero_if_empty(
                                        unsaved_inning['total_extras']
                                    ),
                                    'inning_no': 1 if unsaved_inning[
                                        'team_batting_id'
                                    ] == match_data['batted_first'] else 2,
                                    'complete_innings': True,
                                }
                                inning = coremodels.Inning(**inningargs)
                                inning.match_id = match.id
                                inning.bat_team_id = bat_team.id
                                inning.bowl_team_id = bowl_team.id
                                inning.save()
                                self.no_innings_uploads += 1

                        else:
                            # create two new full innings
                            for i in match_data['innings']:
                                if match_data['home_team_id'] == i['team_batting_id']:
                                    bowl_team_id = match_data['away_team_id']
                                else:
                                    bowl_team_id = match_data['home_team_id']

                                bat_team = pcmodels.Team.objects.filter(
                                    pc_id=i['team_batting_id']
                                )[0].link
                                bowl_team = pcmodels.Team.objects.filter(
                                    pc_id=bowl_team_id
                                )[0].link

                                inningargs = {
                                    'runs': i['runs'] if i['runs'] != '' else 0,
                                    'wickets': i['wickets'] if i['wickets'] != '' else 0,
                                    'overs': i['overs'] if i['overs'] != '' else 0,
                                    'declared': i['declared'],
                                    'extras_byes': i['extra_byes'] if i['extra_byes'] != '' else 0,
                                    'extras_leg_byes': i['extra_leg_byes'] if i['extra_leg_byes'] != '' else 0,
                                    'extras_wides': i['extra_wides'] if i['extra_wides'] != '' else 0,
                                    'extras_no_balls': i['extra_no_balls'] if i['extra_no_balls'] != '' else 0,
                                    'extras_penalties': i['extra_penalty_runs'] if i['extra_penalty_runs'] != '' else 0,
                                    'extras_total': i['total_extras'] if i['total_extras'] != '' else 0,
                                    'inning_no': 1 if i[
                                        'team_batting_id'
                                    ] == match_data['batted_first'] else 2,
                                    'complete_innings': True,
                                }
                                inning = coremodels.Inning(**inningargs)
                                inning.match_id = match.id
                                inning.bat_team_id = bat_team.id
                                inning.bowl_team_id = bowl_team.id
                                inning.save()
                                self.no_innings_uploads += 1

                        # FOR EACH PLAYER CHECK DB to see if a performance already,
                        # exists for a player in that match if it does add to performances

                        # Add all the players and create performances
                        player_performances = {}
                        saved_player_performances = coremodels.Performance.objects.filter(match_id=match.id)
                        unsure_player_performances = saved_player_performances.filter(player_id=1)
                        unsure_player_performances.delete()
                        bat_performances = {}
                        saved_bat_performances = coremodels.BatPerformance.objects.filter(match_id=match.id)
                        unsure_bat_performances = saved_bat_performances.filter(player_id=1)
                        unsure_bat_performances.delete()
                        bowl_performances = {}
                        saved_bowl_performances = coremodels.BowlPerformance.objects.filter(match_id=match.id)
                        unsure_bowl_performances = saved_bowl_performances.filter(player_id=1)
                        unsure_bowl_performances.delete()
                        field_performances = {}
                        saved_field_performances = coremodels.FieldPerformance.objects.filter(match_id=match.id)
                        unsure_field_performances = saved_field_performances.filter(player_id=1)
                        unsure_field_performances.delete()

                        for team in match_data['players']:
                            for k, team in team.iteritems():
                                for eachplayer in team:
                                    # check if player already exists
                                    club = pcmodels.Club.objects.filter(
                                        pc_id=match_data[k[0:4] + '_club_id']
                                    )[0]
                                    players = pcmodels.Player.objects.filter(
                                        pc_id=eachplayer[
                                            'player_id'
                                        ] if eachplayer['player_id'] is not None else 0,
                                        link__club=club.link.id
                                    )
                                    if players.count() == 0:
                                        # Create player in db

                                        playerargs = {
                                            'player_name': eachplayer['player_name'],
                                        }
                                        player = coremodels.Player(**playerargs)
                                        player.club_id = club.link.id
                                        player.save()
                                        pc_player = pcmodels.Player(**{
                                            'pc_id': eachplayer[
                                                'player_id'
                                            ] if eachplayer['player_id'] is not None else 0,
                                        })
                                        pc_player.link_id = player.id
                                        pc_player.save()

                                        self.no_player_uploads += 1
                                    else:
                                        # Fetch current player from db
                                        player = players[0].link

                                    player_performance = saved_player_performances.filter(
                                        player_id=player.id
                                    )
                                    bat_performance = saved_bat_performances.filter(
                                        player_id=player.id
                                    )
                                    bowl_performance = saved_bowl_performances.filter(
                                        player_id=player.id
                                    )
                                    field_performance = saved_field_performances.filter(
                                        player_id=player.id
                                    )

                                    if player_performance.count() == 1:
                                        perf = player_performance[0]
                                        perf.captain = eachplayer['captain']
                                        perf.wicket_keeper = eachplayer[
                                            'wicket_keeper'
                                        ]

                                    else:
                                        perfargs = {
                                            'captain': eachplayer['captain'],
                                            'wicket_keeper': eachplayer['wicket_keeper'],
                                        }
                                        # create performance for each player
                                        perf = coremodels.Performance(**perfargs)
                                        perf.match_id = match.id
                                        perf.player_id = player.id
                                        # Add Performance to performances dict with player_id as key

                                    if bat_performance.count() == 1:
                                        bat_perf = bat_performance[0]
                                    else:
                                        bat_perf = coremodels.BatPerformance()
                                        bat_perf.match_id = match.id
                                        bat_perf.player_id = player.id

                                    if bowl_performance.count() == 1:
                                        bowl_perf = bowl_performances[0]

                                        # Reset stats.
                                        bowl_perf.bowl_wickets_lbw = 0
                                        bowl_perf.bowl_wickets_bowled = 0
                                        bowl_perf.bowl_wickets_stumped = 0
                                        bowl_perf.bowl_wickets_caught = 0
                                        bowl_perf.bowl_wickets_hit_wicket = 0
                                    else:
                                        bowl_perf = coremodels.BowlPerformance()
                                        bowl_perf.match_id = match.id
                                        bowl_perf.player_id = player.id

                                    if field_performance.count() == 1:
                                        field_perf = field_performance[0]

                                        # Reset Stats.
                                        field_perf.field_catches = 0
                                        field_perf.field_run_outs = 0
                                        field_perf.field_stumped = 0

                                    else:
                                        field_perf = coremodels.FieldPerformance()

                                        field_perf.match_id = match.id
                                        field_perf.player_id = player.id

                                    player_performances[
                                        str(eachplayer[
                                            'player_id'
                                        ] if eachplayer['player_id'] is not None else '0_0')
                                    ] = perf
                                    bat_performances[
                                        str(eachplayer[
                                            'player_id'
                                        ] if eachplayer['player_id'] is not None else '0_0')
                                    ] = bat_perf
                                    bowl_performances[
                                        str(eachplayer[
                                            'player_id'
                                        ] if eachplayer['player_id'] is not None else '0_0')
                                    ] = bowl_perf
                                    field_performances[
                                        str(eachplayer[
                                            'player_id'
                                        ] if eachplayer['player_id'] is not None else '0_0')
                                    ] = field_perf
                        # add performance for unsure if it doesn't exist
                        if '0_0' not in player_performances.keys():
                            player_performances['0_0'] = coremodels.Performance(
                                match_id=match.id,
                                player_id=1
                            )
                        if '0_0' not in bat_performances.keys():
                            bat_performances['0_0'] = coremodels.BatPerformance(
                                match_id=match.id,
                                player_id=1
                            )
                        if '0_0' not in bowl_performances.keys():
                            bowl_performances['0_0'] = coremodels.BowlPerformance(
                                match_id=match.id,
                                player_id=1
                            )
                        if '0_0' not in field_performances.keys():
                            field_performances['0_0'] = coremodels.FieldPerformance(
                                match_id=match.id,
                                player_id=1
                            )
                        # process match details to add to performances
                        try:
                            inning_no = 0
                            for inning in match_data['innings']:
                                inning_no += 1
                                total_runs = 0
                                # Add batting data to performances
                                no_batsmen = 0
                                for bat in inning['bat']:
                                    if bat['how_out'] != 'did not bat':
                                        no_batsmen += 1
                                        total_runs += int(bat['runs'] if bat['runs'] != '' else 0)
                                # parScores = self.getParScores(no_batsmen, total_runs)
                                bat_number = 0
                                for bat in inning['bat']:
                                    if bat['batsman_id'] == '':  # check is batsman is unsure
                                        for i in range(num_bat_unsures):
                                            bp = bat_performances['0_' + str(i)]
                                            if not bp.bat:
                                                break  # available performance has been found to enter details
                                            elif i == num_bat_unsures - 1:
                                                # must create new performance as none can be found
                                                num_bat_unsures += 1
                                                bp = coremodels.BatPerformance(
                                                    match_id=match.id,
                                                    player_id=1
                                                )
                                                bat_performances[
                                                    '0_' + str(i + 1)
                                                ] = bp
                                                break
                                    else:
                                        bp = bat_performances[bat['batsman_id']]
                                    bp.bat_position = int(bat['position'])
                                    bp.bat_inning_no = inning_no
                                    # Add how out info
                                    if bat['how_out'] in ['lbw', 'b']:
                                        # batsman was out bowled or lbw
                                        bp.bat_how_out = bat['how_out']
                                        bowler = bowl_performances[
                                            bat['bowler_id'] if bat['bowler_id'] != '' else '0_0'
                                        ]
                                        bp.bat_out_bowler_id = bowler.player_id
                                        bp.bat_out_fielder_id = None
                                        if bat['how_out'] == 'b':
                                            bowler.bowl_wickets_bowled += 1
                                        else:
                                            bowler.bowl_wickets_lbw += 1
                                    elif bat['how_out'] == 'ro':
                                        bp.bat_how_out = bat['how_out']
                                        fielder = field_performances[
                                            bat['fielder_id'] if bat['fielder_id'] != '' else '0_0'
                                        ]
                                        bp.bat_out_bowler_id = None
                                        bp.bat_out_fielder_id = fielder.player_id
                                        fielder.field_run_outs += 1
                                    elif bat['how_out'] in ['ct', 'st']:
                                        bp.bat_how_out = bat['how_out']
                                        bowler = bowl_performances[
                                            bat['bowler_id'] if bat['bowler_id'] != '' else '0_0'
                                        ]
                                        fielder = field_performances[
                                            bat['fielder_id'] if bat['fielder_id'] != '' else '0_0'
                                        ]
                                        bp.bat_out_bowler_id = bowler.player_id
                                        bp.bat_out_fielder_id = fielder.player_id
                                        if bat['how_out'] == 'ct':
                                            bowler.bowl_wickets_caught += 1
                                            fielder.field_catches += 1
                                        else:
                                            bowler.bowl_wickets_stumped += 1
                                            fielder.field_stumped += 1
                                    elif bat['how_out'] == 'no':
                                        bp.bat_how_out = bat['how_out']
                                        bp.bat_out_bowler_id = None
                                        bp.bat_out_fielder_id = None
                                    # Add extra bat info
                                    if bat['how_out'] != 'did not bat':
                                        bp.bat = True
                                        bat_number += 1
                                        bp.bat_runs = bat['runs'] if bat['runs'] != '' else 0
                                        # bp.fours = bat['fours'] if bat['fours'] != '' else 0
                                        # bp.sixes = bat['sixes'] if bat['sixes'] != '' else 0
                                        bp.bat_balls = bat['balls'] if bat['balls'] != '' else 0
                                        # bp.bat_par_score = parScores[bat_number]
                                # Add boling figures to performances
                                bowl_position = 0
                                # Calculate par economy
                                # try:
                                #     bowl_pareconomy = int(inning['runs']) / Performance().overs_conversion(
                                #         inning['overs']
                                #     )
                                # except ZeroDivisionError:
                                #     bowl_pareconomy = 0
                                for bowl in inning['bowl']:
                                    bowl_position += 1
                                    # Fix for multiple unsure players
                                    if bowl['bowler_id'] == '':
                                        for i in range(num_bowl_unsures):
                                            bp = bowl_performances['0_' + str(i)]
                                            if not bp.bowl:
                                                break
                                            elif i == num_bowl_unsures - 1:
                                                num_bowl_unsures += 1
                                                bp = coremodels.BowlPerformance(
                                                    match_id=match.id,
                                                    player_id=1
                                                )
                                                bowl_performances['0_' + str(i + 1)] = bp
                                                break
                                    else:
                                        bp = bowl_performances[
                                            bowl['bowler_id'] if bowl['bowler_id'] != '' else '0'
                                        ]
                                    # Add bowloing info to performances
                                    bp.bowl_position = bowl_position
                                    bp.bowl_overs = bowl['overs'] if bowl['overs'] != '' else 0
                                    bp.bowl_runs = bowl['runs'] if bowl['runs'] != '' else 0
                                    bp.bowl_maidens = bowl['maidens'] if bowl['maidens'] != '' else 0
                                    bp.bowl_wickets_total = bowl['wickets'] if bowl['wickets'] != '' else 0
                                    bp.bowl = True
                                    bp.bowl_inning_no = inning_no
                        except KeyError:
                            match.processing_issue = True
                            self.stdout.write('Issue processing match {}'.format(pc_match.pc_id))
                        else:
                            # save all the performances
                            for k, v in player_performances.iteritems():
                                self.no_performance_uploads += 1
                                v.save()
                            for k, v in bat_performances.iteritems():
                                self.no_performance_uploads += 1
                                v.save()
                            for k, v in bowl_performances.iteritems():
                                self.no_performance_uploads += 1
                                v.save()
                            for k, v in field_performances.iteritems():
                                self.no_performance_uploads += 1
                                v.save()
                            # Save match
                            if not match.is_live_score():
                                match.full_scorecard = True
                            match.save()
                            self.no_full_uploads += 1
                        match.save()
                else:
                    self.no_not_uploaded += 1
                    # Check if match was played or not
                    if match_data[
                            'result'
                    ] in ['A', 'C', 'CON']:
                        # Not played
                        match.full_scorecard = True
                        match.save()
                        self.stdout.write(
                            'Match {} was not played so not uploading'.format(pc_match.pc_id)
                        )
                    elif match_data['result'] == 'M':
                        self.stdout.write('Match {} in progress'.format(pc_match.pc_id))
                    else:
                        # Match played
                        self.stdout.write('Match {} Does not have 2 innings'.format(
                            pc_match.pc_id))
            else:
                self.no_not_uploaded += 1
                self.stdout.write('Issue fetching match {}'.format(
                    pc_match.pc_id))
        except IOError:
            try:
                self.stdout.write('Error processing match {}'.format(pc_match.pc_id))
                match.processing_issue = True
                match.save()
            except:
                self.stdout.write('Error processing match{}')

    def createWorkers(self):
        """ Create Workers/Threads """
        for i in range(1):
            worker = Thread(target=self.fetchResults)
            worker.start()

    def handle(self, *args, **options):
        """ Default command handler """

        for match in pcmodels.Match.objects.filter(
                link__full_scorecard=False,
                link__processing_issue=False,
                link__away_team__club__home_club=True
        ).union(pcmodels.Match.objects.filter(
                link__full_scorecard=False,
                link__processing_issue=False,
                link__home_team__club__home_club=True
        )).distinct():
            # will loop every match that does not have a full scorecard
            if match.link.date.get_date() <= date.today():
                if match.link.home_team.club.home_club:
                    self.process([match])
                else:
                    self.process([match])
                # self.queue.put([match.id, match.fk_team.id])
        # self.createWorkers()
        # self.queue.join()
        # Debug info
        self.stdout.write('{} Basic match info has been uploaded'.format(self.no_basic_uploads))
        self.stdout.write('{} Full match info has been uploaded'.format(self.no_full_uploads))
        self.stdout.write('{} Players have been uploaded'.format(self.no_player_uploads))
        self.stdout.write('{} Innings have been uploaded'.format(self.no_innings_uploads))
        self.stdout.write('{} Performances have been uploaded'.format(self.no_performance_uploads))
        self.stdout.write('{} Matches not uploaded'.format(self.no_not_uploaded))
