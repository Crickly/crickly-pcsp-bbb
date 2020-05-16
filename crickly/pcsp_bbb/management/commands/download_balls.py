# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand

from crickly.playcricket import models as pcmodels
from crickly.pcsp_bbb import models as bbbmodels

import requests
import json
import csv


class Command(BaseCommand):
    help = 'Will download balls for matches'

    def handle(self, *args, **kwargs):

        matches = pcmodels.Match.objects.exclude(match__isnull=False)

        for match in matches:
            pc_match = pcmodels.Match.objects.get(pc_id=match.pc_id)
            uploader = BBBMatchUploader(pc_match)
            uploader.process()

            if len(uploader.balls) > 0:
                bbbmodels.Ball.objects.bulk_create(uploader.balls)
            # with open(f'{match_id}-balls.csv', 'w') as f:
            #     keys = uploader.balls[0].keys()
            #     writer = csv.DictWriter(f, keys)
            #     writer.writeheader()
            #     writer.writerows(uploader.balls)



class BBBMatchUploader(object):

    def __init__(self, pc_match):
        self.pc_match = pc_match
        self.match = pc_match.link
        self.balls = []

        self.bbb_match = bbbmodels.Match(**{
            'match_id': pc_match.id
        })

        r = requests.get(f'https://www.play-cricket.com/website/results/{pc_match.pc_id}')
        print('BALL BY BALL' in r.text)
        if 'BALL BY BALL' in r.text:
            print(f'downloading: {pc_match.id}')

            self.json_data = self.get_json_data(
                (
                    'https://nvplay-gb-api-widgets.nvplay.com/api/scorecard/'
                    '{0}?idType=play-cricket&customerId=5e401d65-10ec-4a28-a0f6-1c084ce30445'
                    '&playerids=true&stats=true&commentary=true'
                    '&callback=jQuery11240636239265092196_1586348797277&_=1586348797278'
                ).format(
                    pc_match.pc_id
                )
            )


            if 'Message' in self.json_data:
                if self.json_data['Message'] == 'An error has occurred.':
                    self.bbb_match.is_pcsp = False
                    print(self.json_data['Message'])
                else:
                    raise Exception('Message: {}'.format(self.json_data['Message']))
            else:
                self.bbb_match.is_pcsp = True
        else:
            self.bbb_match.is_pcsp = False
        self.bbb_match.save()



    def process(self):
        if not self.bbb_match.is_pcsp:
            return

        try:
            self.process_match_data()

            self.process_bbb_data()
            # if self.has_wagon_wheel:
            #     self.process_wagon_wheel_data()
        except Exception as e:
            self.bbb_match.is_error = True
            self.bbb_match.error_text = str(e)
        self.bbb_match.save()

    def process_match_data(self):
        match_data = self.json_data['Match']

        # Match ID
        self.nv_play_match_id = match_data['MatchId']

        # Diff teams nvplay vs crickly
        self.home_team_name = self.match.home_team.club.name + ' ' + self.match.home_team.name
        self.away_team_name = self.match.away_team.club.name + ' ' + self.match.away_team.name

        if self.home_team_name == match_data['Team1ExternalName']:
            self.team_1 = self.match.home_team
            self.team_2 = self.match.away_team
        elif self.away_team_name == match_data['Team1ExternalName']:
            self.team_1 = self.match.away_team
            self.team_2 = self.match.home_team
        else:
            # Try with Team2, if not weve failed :'(
            if self.home_team_name == match_data['Team2ExternalName']:
                self.team_2 = self.match.home_team
                self.team_1 = self.match.away_team
            elif self.away_team_name == match_data['Team2ExternalName']:
                self.team_2 = self.match.away_team
                self.team_1 = self.match.home_team
            else:
                raise Exception('Failed to diff teams.')

        # Diff the players
        self.team_1_players = PlayerManager(
            match_data['Team1Players'],
            self.team_1.club.id,
            self.match.id
        )
        self.team_2_players = PlayerManager(
            match_data['Team2Players'],
            self.team_2.club.id,
            self.match.id
        )

        self.has_wagon_wheel = match_data['HasWagonWheelData']

    def process_bbb_data(self):
        for inning_no, inning in enumerate(self.json_data['Innings']):
            self.balls += self.process_bbb_innings_data(inning_no, inning)

    def process_bbb_innings_data(self, inning_no, inning_data):
        batting_card_lookup = {
            k: card for k, card in enumerate(inning_data['BattingCard'], 1) if card['Id'] is not None
        }
        bowling_card_lookup = {
            k: card for k, card in enumerate(inning_data['BowlingCard'], 1) if card['Id'] is not None
        }

        first_batsman_id = batting_card_lookup[next(iter(batting_card_lookup))]['Id']
        if first_batsman_id in self.team_1_players:
            batting_players = self.team_1_players
            bowling_players = self.team_2_players
        else:
            batting_players = self.team_2_players
            bowling_players = self.team_1_players


        match_state = {
            'total_balls': 0,
            'total_runs': 0,
            'total_wickets': 0,
            'total_extras': 0,
            'on_strike': 1,
            'non_strike': 2,
        }

        for player in batting_card_lookup:
            batting_card_lookup[player]['total_batsman_runs'] = 0
            batting_card_lookup[player]['total_batsman_balls'] = 0

        for player in bowling_card_lookup:
            bowling_card_lookup[player]['total_bowler_balls'] = 0
            bowling_card_lookup[player]['total_bowler_runs'] = 0
            bowling_card_lookup[player]['total_bowler_wickets'] = 0

        balls = []
        for over in inning_data['Overs']:
            over_number = over['OverNo']
            for ball_number, ball in enumerate(over['Balls'], 1):

                if ball['bt'] != match_state['on_strike']:
                    match_state['on_strike'], match_state['non_strike'] =\
                    match_state['non_strike'], match_state['on_strike']


                is_wicket = False
                how_out = ''
                out_batsman_id = None
                fielder_id = None
                if self.is_wicket(ball):
                    is_wicket = True
                    out_batsman_id, out_batsman_index, fielder_id, how_out = self.get_wicket_details(
                        ball,
                        match_state,
                        batting_card_lookup,
                        batting_players,
                        bowling_players
                    )

                runs, bat_runs, extra_runs, wides, noballs, byes, leg_byes = self.get_runs(ball)

                batsman_id, non_striker_id, bowler_id = self.get_players(
                    ball,
                    match_state,
                    batting_card_lookup, batting_players,
                    bowling_card_lookup, bowling_players
                )

                # Update match state
                match_state['total_balls'] += 1
                match_state['total_runs'] += runs
                match_state['total_extras'] += extra_runs

                bowling_card_lookup[ball['bl']]['total_bowler_balls'] += 1
                bowling_card_lookup[ball['bl']]['total_bowler_runs'] += bat_runs + wides + noballs

                batting_card_lookup[ball['bt']]['total_batsman_balls'] += 1
                batting_card_lookup[ball['bt']]['total_batsman_runs'] += bat_runs

                if is_wicket:
                    match_state['total_wickets'] += 1

                    if how_out in ['Bowled', 'Caught', 'LBW', 'Stumped', 'Hitwicket']:
                        bowling_card_lookup[ball['bl']]['total_bowler_wickets'] += 1


                balls.append(bbbmodels.Ball(**{
                    'ball_key': ball['BallKey'],
                    'match_id': self.match.id,
                    'innings_number': inning_no,
                    'over_number': over_number,
                    'ball_number': ball_number,

                    'batsman_id': batsman_id,
                    'non_striker_id': non_striker_id,
                    'bowler_id': bowler_id,
                    'fielder_id': fielder_id,

                    'runs': runs,
                    'bat_runs': bat_runs,
                    'extra_runs': extra_runs,
                    'wides': wides,
                    'noballs': noballs,
                    'byes': byes,
                    'leg_byes': leg_byes,

                    'is_wicket': is_wicket,
                    'out_batsman_id': out_batsman_id,
                    'how_out': how_out,

                    'total_balls': match_state['total_balls'],
                    'total_bowler_balls': bowling_card_lookup[ball['bl']]['total_bowler_balls'],
                    'total_batsman_balls': batting_card_lookup[ball['bt']]['total_batsman_balls'],

                    'total_runs': match_state['total_runs'],
                    'total_bat_runs': batting_card_lookup[ball['bt']]['total_batsman_runs'],
                    'total_bowl_runs': bowling_card_lookup[ball['bl']]['total_bowler_runs'],
                    'total_extra_runs': match_state['total_extras'],

                    'total_wickets': match_state['total_wickets'],
                    'total_bowler_wickets': bowling_card_lookup[ball['bl']]['total_bowler_wickets'],

                    'wagon_x': ball['x'],
                    'wagon_y': ball['y'],
                }))

                if is_wicket:
                    # change the match state striker/nonstriker value for the out player
                    new_bat_index = max([match_state['on_strike'], match_state['non_strike']]) + 1
                    if out_batsman_index == match_state['on_strike']:
                        match_state['on_strike'] = new_bat_index
                    else:
                        match_state['non_strike'] = new_bat_index
        return balls

    def is_wicket(self, ball):
        return 'W' in ball['Display']

    def get_wicket_details(
            self,
            ball,
            match_state,
            batting_card_lookup,
            batting_players,
            bowling_players
    ):
        # Get player who is out.
        on_strike = batting_card_lookup[match_state['on_strike']]
        non_strike = batting_card_lookup[match_state['non_strike']]

        def dismissal_string(bat_card):
            return bat_card['PlayerName'].strip('*†') + ' ' + bat_card['HowOut']

        out_player_id = None
        out_player_index = None
        if dismissal_string(on_strike) in ball['C']:
            out_player_id = batting_players.player_dict[on_strike['Id']]['player'].id
            out_player_index = match_state['on_strike']
        elif dismissal_string(non_strike) in ball['C']:
            out_player_id = batting_players.player_dict[non_strike['Id']]['player'].id
            out_player_index = match_state['non_strike']
        else:
            print(ball)
            print(dismissal_string(on_strike))
            print(dismissal_string(non_strike))
            raise Exception('Dunno who is out')

        how_out = batting_card_lookup[out_player_index]['Dismissal']['Type']
        fielder_id = None
        if how_out in ['Caught', 'RunOut', 'Stumped']:
            try:
                fielder_id = bowling_players.player_dict[batting_card_lookup[
                    out_player_index
                ]['Dismissal']['Fielders'][0]['Id']]['player'].id
            except KeyError:
                pass

        return out_player_id, out_player_index, fielder_id, how_out

    def get_runs(self, ball):
        if ball['Display'] in ['.', 'W']:
            # Dot ball
            return 0, 0, 0, 0, 0, 0, 0
        ball['Display'] = ball['Display'].replace('W', '')
        if 'w' in ball['Display']:
            # Wide ball
            wides = 1
            if '+' in ball['Display']:
                wides += int(ball['Display'].split('+')[1])
            return wides, 0, wides, wides, 0, 0, 0
        if 'nb' in ball['Display']:
            noballs = 1
            bat_runs = 0
            byes = 0
            leg_byes = 0
            if '+' in ball['Display']:
                first_half = ball['Display'].split('+')[0]
                if 'lb' in first_half:
                    leg_byes = int(first_half.strip('lb'))
                elif 'b' in first_half:
                    byes = int(first_half.strip('b'))
                else:
                    bat_runs = int(first_half)

            return noballs + bat_runs + byes + leg_byes, bat_runs, noballs + byes + leg_byes, \
                0, noballs, byes, leg_byes

        if 'lb' in ball['Display']:
            leg_byes = int(ball['Display'].strip('lb'))
            return leg_byes, 0, leg_byes, 0, 0, 0, leg_byes

        if 'b' in ball['Display']:
            byes = int(ball['Display'].strip('b'))
            return byes, 0, byes, 0, 0, byes, 0

        runs = int(ball['Display'])
        return runs, runs, 0, 0, 0, 0, 0

    def get_players(
            self,
            ball,
            match_state,
            batting_card_lookup,
            batting_players,
            bowling_card_lookup,
            bowling_players
    ):
        _batsman_id = batting_card_lookup[match_state['on_strike']]['Id']
        batsman_id = batting_players.player_dict[
            _batsman_id
        ]['player'].id

        _non_striker_id = batting_card_lookup[match_state['non_strike']]['Id']
        non_striker_id = batting_players.player_dict[
            _non_striker_id
        ]['player'].id

        _bowler_id = bowling_card_lookup[ball['bl']]['Id']
        bowler_id = bowling_players.player_dict[
            _bowler_id
        ]['player'].id


        return batsman_id, non_striker_id, bowler_id

    @staticmethod
    def get_json_data(url):
        r = requests.get(url)
        if r.status_code != 200:
            try:
                return json.loads(r.text[r.text.find('(')+1: r.text.rfind(')')])
            except:
                raise Exception('Request failed, had status code of {}'.format(r.status_code))
        return json.loads(r.text[r.text.find('(')+1: r.text.rfind(')')])


class PlayerManager(object):
    def __init__(self, nvplay_players, club_id, match_id):
        self.match_id = match_id
        self.player_dict = {
            player['Id']: self.get_player_obj(player, club_id) for player in nvplay_players
        }

    def get_player_obj(self, nv_play_player, club_id):
        try:
            player = pcmodels.Player.objects.get(
                pc_id=nv_play_player['ExternalId'],
                link__club_id=club_id
            )
        except:
            player = pcmodels.Player.objects.get(
                link__club_id=club_id,
                link__performance__match_id=self.match_id,
                link__player_name=nv_play_player['Name'].strip('*†')
            )

        return {
            'pc_id': player.pc_id,
            'name': nv_play_player['Name'].strip('*†'),
            'captain': nv_play_player['IsCaptain'],
            'keeper': nv_play_player['IsWicketKeeper'],
            'twelth_man': nv_play_player['IsTwelthMan'],
            'player': player.link,
        }

    def __contains__(self, value):
        return value in self.player_dict

