# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# Django Imports
from django.core.management.base import BaseCommand
from django.conf import settings

# 3rd Party Imports
from queue import Queue
from threading import Thread
from datetime import datetime
import requests
import json

# App Imports
from crickly.core import models as coremodels
from crickly.playcricket import models as pcmodels


class Command(BaseCommand):
    help = 'will fetch all current and previous matches'
    API_URL = 'http://www.play-cricket.com/api/v2/'
    queue = Queue(maxsize=0)  # Creates infinite size queue

    def get_data(self, url):
        """ Gets JSON data from play-cricket API """
        r = requests.get(
            self.API_URL + url + '&api_token={}'.format(settings.PC_API_KEY)
        )
        if r.ok:  # check is api response is valid
            return json.loads(r.content)
        else:
            r.raise_for_status()

    def save_detail(self, cls, save_data, pc_id):
        corecls = cls.cricket_model()
        pc_instance = cls.objects.filter(pc_id=pc_id)

        if pc_instance.exists():
            instance = pc_instance[0].link
        else:
            instance = corecls.objects.create(**save_data)
            instance.save()
            pc_instance = cls.objects.create(**{
                'pc_id': pc_id,
                'link_id': instance.id,
            })
            pc_instance.save()
        return instance.id

    def process(self, match):
        """ Worker function """
        try:
            match_id = str(match['match_id'])
            match_data = self.get_data(
                'match_detail.json?match_id={}'.format(match_id)
            )['match_details'][0]  # Gets match data from API
            # print(match_data)
            if match_id == str(match_data['id']):  # Check correct match is returned
                # create match model
                if pcmodels.Match.objects.filter(pc_id=match_id).count() == 0:  # if not in database

                    # Create matchargs dictionary. With all match data
                    matchargs = {
                        'status': match_data['status'],
                        'last_updated': datetime.strptime(
                            match_data['last_updated'],
                            '%d/%m/%Y'
                        ).date().isoformat(),  # Get date into correct format
                        # 'competition_name': match_data['competition_name'],
                        # 'competition_id': match_data['competition_id'],
                        # 'competition_type': match_data['competition_type'],
                        'match_type': match_data['match_type'],
                        'game_type': match_data['game_type'],
                        # 'match_id': match_data['match_id'],
                        # 'match_date': datetime.strptime(
                        #     match_data['match_date'],
                        #     '%d/%m/%Y'
                        # ).date().isoformat(),
                        # 'ground_name': match_data['ground_name'],
                        # 'ground_id': match_data['ground_id'],
                        # 'home_team_name': match_data['home_team_name'],
                        # 'home_team_id': match_data['home_team_id'],
                        # 'home_club_name': match_data['home_club_name'],
                        # 'home_club_id': match_data['home_club_id'],
                        # 'away_team_name': match_data['away_team_name'],
                        # 'away_team_id': match_data['away_team_id'],
                        # 'away_club_name': match_data['away_club_name'],
                        # 'away_club_id': match_data['away_club_id'],
                        'toss_won_by_team_id': match_data['toss_won_by_team_id'],
                        'toss': match_data['toss'],
                        'batted_first': match_data['batted_first'],
                        'result': match_data['result'],
                        'result_description': match_data['result_description'],
                        'result_applied_to': match_data['result_applied_to'],
                        'match_notes': match_data['match_notes'],
                        # 'season': datetime.strptime(match_data['match_date'], '%d/%m/%Y').year
                    }
                    # if match_data['umpire_1_id'] != '':  # add umpire 1 if they exist
                    #     matchargs['umpire_1_id'] = match_data['umpire_1_id']
                    #     matchargs['umpire_1_name'] = match_data['umpire_1_name']
                    # if match_data['umpire_2_id'] != '':  # add umpire 2 if they exist
                    #     matchargs['umpire_2_id'] = match_data['umpire_2_id']
                    #     matchargs['umpire_2_name'] = match_data['umpire_2_name']
                    match = coremodels.Match(**matchargs)  # creates match instance with 'matchargs' data

                    # NEW Match Storage
                    # Clubs
                    home_club_id = self.save_detail(
                        pcmodels.Club,
                        {
                            'name': match_data['home_club_name'],
                        },
                        match_data['home_club_id']
                    ) if match_data['home_club_id'] != '' else 1
                    away_club_id = self.save_detail(
                        pcmodels.Club,
                        {
                            'name': match_data['away_club_name'],
                        },
                        match_data['away_club_id']
                    ) if match_data['away_club_id'] != '' else 1

                    # Teams
                    match.home_team_id = self.save_detail(
                        pcmodels.Team,
                        {
                            'name': match_data['home_team_name'],
                            'club_id': home_club_id,
                        },
                        match_data['home_team_id']
                    )
                    match.away_team_id = self.save_detail(
                        pcmodels.Team,
                        {
                            'name': match_data['away_team_name'],
                            'club_id': away_club_id,
                        },
                        match_data['away_team_id']
                    )

                    league_id = self.save_detail(
                        pcmodels.League,
                        {
                            'name': match_data['league_name'],
                        },
                        match_data['league_id']
                    ) if match_data['league_id'] != '' else 1

                    # Competition
                    match.competition_id = self.save_detail(
                        pcmodels.Competition,
                        {
                            'name': match_data['competition_name'],
                            'competition_type': match_data['competition_type'],
                            'league_id': league_id,
                        },
                        match_data['competition_id']
                    ) if match_data['competition_id'] != '' else 1

                    # Ground
                    match.ground_id = self.save_detail(
                        pcmodels.Ground,
                        {
                            'name': match_data['ground_name'],
                            'club_id': home_club_id,
                        },
                        match_data['ground_id']
                    ) if match_data['ground_id'] != '' else 1

                    # Match Date
                    match_date = datetime.strptime(match_data['match_date'], '%d/%m/%Y').date()
                    if coremodels.MatchDate.objects.filter(
                            year=match_date.year,
                            month=match_date.month,
                            day=match_date.day,
                    ).exists():
                        match_date = coremodels.MatchDate.objects.filter(
                            year=match_date.year,
                            month=match_date.month,
                            day=match_date.day,
                        )[0]
                    else:
                        match_date = coremodels.MatchDate.objects.create(
                            year=match_date.year,
                            month=match_date.month,
                            day=match_date.day,
                            date=match_date,
                        )
                    match.date_id = match_date.id

                    match.save()  # Saves match to database

                    pc_match = pcmodels.Match(
                        pc_id=match_id
                    )
                    pc_match.link_id = match.id
                    pc_match.save()
                    self.stdout.write('Match {} saved with id {}'.format(match_id, match.id))
                else:
                    # check last update date to see if there are any modifications
                    match = pcmodels.Match.objects.filter(pc_id=match_id)[0].link
                    if match.last_updated <= datetime.strptime(
                        match_data['last_updated'],
                        '%d/%m/%Y'
                    ).date():
                        # OLD Match Storage

                        # change has occurred resave data
                        match.status = match_data['status']
                        match.last_updated = datetime.strptime(
                            match_data['last_updated'],
                            '%d/%m/%Y'
                        ).date().isoformat()
                        # match.competition_name = match_data['competition_name']
                        # match.competition_id = match_data['competition_id']
                        # match.competition_type = match_data['competition_type']
                        match.match_type = match_data['match_type']
                        match.game_type = match_data['game_type']
                        # match.match_id = match_data['match_id']
                        # match.match_date = datetime.strptime(
                        #     match_data['match_date'],
                        #     '%d/%m/%Y'
                        # ).date().isoformat()
                        # match.ground_name = match_data['ground_name']
                        # match.ground_id = match_data['ground_id']
                        # match.home_team_name = match_data['home_team_name']
                        # match.home_team_id = match_data['home_team_id']
                        # match.home_club_name = match_data['home_club_name']
                        # match.home_club_id = match_data['home_club_id']
                        # match.away_team_name = match_data['away_team_name']
                        # match.away_team_id = match_data['away_team_id']
                        # match.away_club_name = match_data['away_club_name']
                        # match.away_club_id = match_data['away_club_id']
                        match.toss_won_by_team_id = match_data['toss_won_by_team_id']
                        match.toss = match_data['toss']
                        match.batted_first = match_data['batted_first']
                        match.result = match_data['result']
                        match.result_description = match_data['result_description']
                        match.result_applied_to = match_data['result_applied_to']
                        match.match_notes = match_data['match_notes']

                        # NEW Match Storage

                        # Clubs
                        home_club_id = self.save_detail(
                            pcmodels.Club,
                            {
                                'name': match_data['home_club_name'],
                            },
                            match_data['home_club_id']
                        ) if match_data['home_club_id'] != '' else 1
                        away_club_id = self.save_detail(
                            pcmodels.Club,
                            {
                                'name': match_data['away_club_name'],
                            },
                            match_data['away_club_id']
                        ) if match_data['away_club_id'] != '' else 1

                        # Teams
                        match.home_team_id = self.save_detail(
                            pcmodels.Team,
                            {
                                'name': match_data['home_team_name'],
                                'club_id': home_club_id,
                            },
                            match_data['home_team_id']
                        )
                        match.away_team_id = self.save_detail(
                            pcmodels.Team,
                            {
                                'name': match_data['away_team_name'],
                                'club_id': away_club_id,
                            },
                            match_data['away_team_id']
                        )

                        # Competition
                        match.competition_id = self.save_detail(
                            pcmodels.Competition,
                            {
                                'name': match_data['competition_name'],
                                'competition_type': match_data['competition_type'],
                            },
                            match_data['competition_id']
                        ) if match_data['competition_id'] != '' else 1

                        # Ground
                        match.ground_id = self.save_detail(
                            pcmodels.Ground,
                            {
                                'name': match_data['ground_name'],
                                'club_id': home_club_id,
                            },
                            match_data['ground_id']
                        ) if match_data['ground_id'] != '' else 1

                        # Match Date
                        match_date = datetime.strptime(match_data['match_date'], '%d/%m/%Y').date()
                        if coremodels.MatchDate.objects.filter(
                                year=match_date.year,
                                month=match_date.month,
                                day=match_date.day,
                        ).exists():
                            match_date = coremodels.MatchDate.objects.filter(
                                year=match_date.year,
                                month=match_date.month,
                                day=match_date.day,
                            )[0]
                        else:
                            match_date = coremodels.MatchDate.objects.create(
                                year=match_date.year,
                                month=match_date.month,
                                day=match_date.day,
                                date=match_date
                            )
                        match.fk_date_id = match_date.id

                        match.save()  # Save match to data base
            else:
                # Match fetched was not match requested
                self.stdout.write('Issue fetching match: {}'.format(match_id))
        except:
            self.stdout.write('Error processing match: {}'.format(match_id))

    def createWorkers(self):
        for i in range(1):
            worker = Thread(target=self.save_match)
            worker.start()  # Starts workers

    def handle(self, *args, **options):
        """ Default command handler. Run after __init__ """
        clubs = pcmodels.Club.objects.filter(link__home_club=True)
        for club in clubs:
            club_id = club.pc_id
            # teams = pcmodels.Team.objects.filter(link__club_id=club.link.id)
            # teams = PlayCricketTeam.objects.filter(active=True)
            # for team in teams:  # For each team defined in settings
                # self.stdout.write('Next team {}'.format(team.link.name))
                # season_range = [datetime.now().year]
                # Remove comment below on first run!!
            season_range = range(
                int(2017),
                int(datetime.now().year) + 1,
                1
            )
            for i in season_range:  # for each season till current one
                self.stdout.write('next season {}'.format(i))
                matches = self.get_data(
                    # 'matches.json?&site_id={}&season={}&team_id={}'.format(club_id, i, team.pc_id)
                    'matches.json?&site_id={}&season={}'.format(club_id, i)
                )['matches']  # fetches matches for team and season
                for match in matches:
                    # for each match in data requested
                    # Checks match status is new and published, and not currently in database
                    if match['status'] == 'New' and match['published'] == 'Yes':
                        # self.queue.put({
                        #     'match_id': match['id'],
                        #     'team': team
                        # })  # Adds match id to queue
                        self.process({
                            'match_id': match['id'],
                            # 'team': team,
                        })
                        self.stdout.write('Added {} to queue'.format(match['id']))
        self.stdout.write('Matches have been saved')
