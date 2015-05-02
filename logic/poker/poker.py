__author__ = 'reut'

from random import choice
from logic.deck import *
from collections import defaultdict
from logic.poker.players import *


class Pot(object):

    def __init__(self, small_blind):
        self.current_bet = small_blind * 2
        self.bets = defaultdict(int)
        self.last_raise = small_blind

    def player_bet(self, player):
        return self.bets[player]

    def amount_to_call(self, player):
        return self.current_bet - self.bets[player]

    def minimum_to_bet(self, player):
        return self.current_bet + self.last_raise - self.player_bet(player)

    def take_pot_for_player(self, player):
        player_bet = self.player_bet(player)

        winnings = 0
        # take amount from all bets
        for player, bet in self.bets.items():
            # see how much is possible to take from player
            possible_to_take = min(bet, player_bet)
            winnings += possible_to_take
            # remove as much as possible from player
            self.bets[player] -= possible_to_take

        return winnings

    def bet(self, player, amount):
        self.bets[player] += amount


class Round(object):

    def __init__(self, players, button_player, small_blind):
        self.players = players[:]
        self.folded_players = []
        self.small_blind = small_blind
        self.betting_player = None
        self.pot = None
        self.deck = Deck()
        self.community_cards = []
        self.button_player = button_player
        self.pot = Pot(self.small_blind)
        LOGGER.info("Dealing cards")
        for player in self.players:
            player.set_pocket(self.deck.draw(), self.deck.draw())
            player.first_bet = True
            player.folded = False

    def bet(self, player, amount):
        self.pot.bet(player, amount)

    def is_folded(self, player):
        return player in self.folded_players

    @property
    def active_players(self):
        return [player for player in self.players if player not in self.folded_players]

    def after(self, player):
        index = self.players.index(player)
        return self.players[(index + 1) % len(self.players)]

    def take_blinds(self):
        self.small_blind_player().force_bet(self.small_blind, self)
        self.big_blind_player().force_bet(2 * self.small_blind, self)
        return self.betting_player

    def small_blind_player(self):
        return self.after(self.button_player)

    def big_blind_player(self):
        return self.after(self.after(self.button_player))

    def winner(self):
        # check if only a single player is left
        return self.players[0] if len(self.players) - len(self.folded_players) == 1 else None

    def pre_flop_betting(self):
        if self.winner() is not None:
            return
        self.betting_player = self.after(self.big_blind_player())
        self.place_bets()

    def pre_turn_betting(self):
        if self.winner() is not None:
            return
        self.betting_player = self.after(self.button_player)
        self.place_bets()

    def pre_river_betting(self):
        if self.winner() is not None:
            return
        self.betting_player = self.after(self.button_player)
        self.place_bets()

    def next_betting_player(self):
        start = self.betting_player
        candidate = self.after(start)
        while candidate is not start:
            if candidate.is_betting(self):
                LOGGER.info("Found betting player %s" % candidate)
                return candidate
            LOGGER.info("Skipping player %s" % candidate)
            candidate = self.after(candidate)
        return None

    def place_bets(self):
        # when no betting players are left
        # self.betting_player will be set to None

        if not self.betting_player.is_betting(self):
            LOGGER.info("Skipping player: %s" % str(self.betting_player))
            self.betting_player = self.next_betting_player()

        while self.betting_player is not None:
            action = self.betting_player.interact(self)
            LOGGER.info("%s chose Action: %s" % (self.betting_player.name, action.__class__.__name__))
            action.apply()
            self.betting_player = self.next_betting_player()

        LOGGER.info("Done betting for pre_flop_round")

    def play(self):

        while self.winner() is None:

            LOGGER.info("Playing another round of poker")

            self.take_blinds()

            LOGGER.info("Playing first round (pre-flop)")
            self.pre_flop_betting()
            self.open_flop_cards()

            LOGGER.info("Playing first round (pre-turn)")
            self.pre_turn_betting()
            self.open_turn_cards()

            LOGGER.info("Playing first round (pre-river)")
            self.pre_river_betting()
            self.open_river_cards()

        LOGGER.info("Round winner: %s" % self.winner())

    def open_card(self):
        self.community_cards.append(self.deck.draw())

    def open_flop_cards(self):
        self.open_card()
        self.open_card()
        self.open_card()

    def open_turn_cards(self):
        self.open_card()

    def open_river_cards(self):
        self.open_card()

    def finish_round(self):
        for winner in self.get_round_winners():
            LOGGER.info("Giving pot to player: " + winner.name)
            winner.money += self.pot.take_pot_for_player(winner)

    def get_round_winners(self):
        return sorted(set(self.players) - set(self.folded_players), key=lambda x: x.best_hand(self.community_cards))


class Poker(object):

    def __init__(self, players):

        # list of players who ran out of money
        self.finished_players = []

        # list of all players in game
        self.players = players

        self.button_player = choice(self.players)
        self.small_blind = 1
        self.rounds = []

    def winner(self):
        """
        :return: game's winner, if one exists (None otherwise)
        """
        return self.players[0] if len(self.players) == 1 else None

    def after(self, player):
        wanted_player_index = (self.players.index(player) + 1) % len(self.players)
        return self.players[wanted_player_index]

    def advance_button_player(self):
        self.button_player = self.after(self.button_player)
        while self.button_player.money == 0:
            # keep searching for valid button player
            self.button_player = self.after(self.button_player)

    def play(self):
        while self.winner() is None:
            LOGGER.info("Playing round #%d" % (len(self.rounds) + 1))
            LOGGER.info("Players are:")
            for player in self.players:
                LOGGER.info("%s" % player)
            round_ = Round(self.players, self.button_player, self.small_blind)
            round_.play()
            self.rounds.append(round_)

            # move button (before possibly removing button player)
            self.advance_button_player()

            # give winners their money
            for winner in round_.get_round_winners():
                LOGGER.info("Giving money to winner: %s" % winner)
                winner_money = round_.pot.take_pot_for_player(winner)
                LOGGER.info("won: %d" % winner_money)
                winner.money += winner_money
            # set up players
            for player in self.players:
                if player.money == 0:
                    LOGGER.info("Player %s finished the game" % str(player))
                    self.finished_players.append(player)
                    self.players.remove(player)


if __name__ == "__main__":
    LOGGER.info("Starting a pvp poker game")
    game = Poker([HumanPlayer("Human %d" % i, 100) for i in range(2)])
    game.play()