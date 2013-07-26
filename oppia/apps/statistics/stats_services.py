# coding: utf-8
#
# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Services for Oppia statistics."""

__author__ = 'Sean Lip'

import collections

import feconf
from oppia.apps.exploration import exp_domain
import oppia.apps.state.models as state_models
import oppia.apps.statistics.models as stats_models
import utils


IMPROVE_TYPE_DEFAULT = 'default'
IMPROVE_TYPE_INCOMPLETE = 'incomplete'

STATS_ENUMS = utils.create_enum(
    'exploration_visited', 'rule_hit', 'exploration_completed',
    'feedback_submitted', 'state_hit', 'unresolved_answers')


def get_event_id(event_name, eid):
    if event_name == STATS_ENUMS.exploration_visited:
        return 'e.%s' % eid
    if event_name == STATS_ENUMS.rule_hit:
        return 'default.%s' % eid
    if event_name == STATS_ENUMS.exploration_completed:
        return 'c.%s' % eid
    if event_name == STATS_ENUMS.feedback_submitted:
        return 'f.%s' % eid
    if event_name == STATS_ENUMS.state_hit:
        return 's.%s' % eid
    if event_name == STATS_ENUMS.unresolved_answers:
        return 'u.%s' % eid


class EventHandler(object):
    """Records events."""

    @classmethod
    def _record_event(cls, event_name, eid, extra_info=''):
        """Updates statistics based on recorded events."""

        event_id = get_event_id(event_name, eid)

        if event_name == STATS_ENUMS.exploration_visited:
            cls._inc(event_id)
        if event_name == STATS_ENUMS.rule_hit:
            cls._add(event_id, unicode(extra_info))
        if event_name == STATS_ENUMS.exploration_completed:
            cls._inc(event_id)
        if event_name == STATS_ENUMS.feedback_submitted:
            cls._add(event_id, unicode(extra_info))
        if event_name == STATS_ENUMS.state_hit:
            cls._inc(event_id)
        if event_name == STATS_ENUMS.unresolved_answers:
            cls._add_data_point_to_tally(event_id, unicode(extra_info))

    @classmethod
    def record_rule_hit(cls, exploration_id, state_id, rule, extra_info=''):
        """Records an event when an answer triggers the default rule."""
        cls._record_event(
            STATS_ENUMS.rule_hit, '%s.%s.%s' % (exploration_id, state_id, rule),
            extra_info=extra_info)

    @classmethod
    def record_exploration_visited(cls, exploration_id):
        """Records an event when an exploration is first loaded."""
        cls._record_event(STATS_ENUMS.exploration_visited, exploration_id)

    @classmethod
    def _record_exploration_completed(cls, exploration_id):
        """Records an event when an exploration is completed."""
        cls._record_event(STATS_ENUMS.exploration_completed, exploration_id)

    @classmethod
    def record_feedback_submitted(cls, url, feedback):
        """Records an event where feedback was submitted via the web UI."""
        cls._record_event(
            STATS_ENUMS.feedback_submitted, url, extra_info=feedback
        )

    @classmethod
    def record_state_hit(cls, exploration_id, state_id):
        """Record an event when a state is loaded."""
        if state_id == feconf.END_DEST:
            cls._record_exploration_completed(exploration_id)
        else:
            cls._record_event(STATS_ENUMS.state_hit, '%s.%s' %
                              (exploration_id, state_id))

    @classmethod
    def record_unresolved_answer(cls, exploration_id, state_id, answer):
        """Records a new unresolved answer."""
        cls._record_event(
            STATS_ENUMS.unresolved_answers,
            '%s.%s' % (exploration_id, state_id),
            extra_info=answer
        )

    @classmethod
    def replace_unresolved_answers(cls, exploration_id, state_id, new_value):
        cls._set_tally(get_event_id(
            STATS_ENUMS.unresolved_answers,
            '%s.%s' % (exploration_id, state_id)
        ), new_value)

    @classmethod
    def _inc(cls, event_id):
        """Increments the counter corresponding to an event id."""
        counter = stats_models.Counter.get(event_id, strict=False)
        if not counter:
            counter = stats_models.Counter(id=event_id)
        counter.value += 1
        counter.put()

    @classmethod
    def _add(cls, event_id, value):
        """Adds to the list corresponding to an event id."""
        journal = stats_models.Journal.get(event_id, strict=False)
        if not journal:
            journal = stats_models.Journal(id=event_id)
        journal.values.append(value)
        journal.put()

    @classmethod
    def _add_data_point_to_tally(cls, event_id, data):
        """Adds a data point to a tally."""
        tally = stats_models.Tally.get(event_id, strict=False)
        if tally is None:
            tally = stats_models.Tally(id=event_id, value={})

        if data in tally.value:
            tally.value[data] += 1
        else:
            tally.value[data] = 1

        tally.put()

    @classmethod
    def _set_tally(cls, event_id, new_value):
        """Sets the value of a tally."""
        tally = stats_models.Tally.get(event_id, strict=False)
        if tally:
            tally.value = new_value
            tally.put()

    @classmethod
    def _append_to_log(cls, event_id, value):
        """Adds to the list corresponding to an event id."""
        journal = stats_models.Journal.get(event_id, strict=False)
        if not journal:
            journal = stats_models.Journal(id=event_id)
        journal.values.append(value)
        journal.put()


def _count_state_hits(exploration_id, state_id):
    """Returns the number of times a particular state was entered."""
    state_key = '.'.join([exploration_id, state_id])
    event_id = get_event_id(STATS_ENUMS.state_hit, state_key)
    return stats_models.Counter.get_value_by_id(event_id)


def get_unresolved_answers(exploration_id, state_id):
    """Gets the tally of unresolved answers for a given state."""
    state_key = '.'.join([exploration_id, state_id])
    event_id = get_event_id(STATS_ENUMS.unresolved_answers, state_key)
    return stats_models.Tally.get_value_by_id(event_id)


def get_exploration_stats(event_name, exploration_id):
    """Retrieves statistics for the given event name and exploration id."""

    if (event_name in [STATS_ENUMS.exploration_visited,
                       STATS_ENUMS.exploration_completed]):
        event_id = get_event_id(event_name, exploration_id)
        return stats_models.Counter.get_value_by_id(event_id)

    if event_name == STATS_ENUMS.rule_hit:
        result = {}

        exploration = exp_domain.Exploration.get(exploration_id)
        for state_id in exploration.state_ids:
            state = exploration.get_state_by_id(state_id)
            result[state.id] = {
                'name': state.name,
                'rules': {}
            }
            for handler in state.widget.handlers:
                for rule in handler.rule_specs:
                    rule_name = str(rule)
                    event_id = get_event_id(
                        event_name, '.'.join(
                            [exploration_id, state.id, rule_name]))

                    journal = stats_models.Journal.get(event_id, strict=False)
                    result[state.id]['rules'][rule_name] = {
                        'answers': collections.Counter(
                            journal.values).most_common(10) if journal else [],
                    }

        return result

    if event_name == STATS_ENUMS.state_hit:
        result = {}

        exploration = exp_domain.Exploration.get(exploration_id)
        for state_id in exploration.state_ids:
            state = exploration.get_state_by_id(state_id)
            result[state.id] = {
                'name': state.name,
                'count': _count_state_hits(exploration_id, state_id)
            }
        return result


def get_top_ten_improvable_states(explorations):
    ranked_states = []
    for exploration in explorations:
        for state_id in exploration.state_ids:
            state = exploration.get_state_by_id(state_id)

            # Count how many times the state was hit.
            all_count = _count_state_hits(exploration.id, state.id)
            if all_count == 0:
                continue

            # Count the number of times the default rule was hit.
            event_id = get_event_id(
                STATS_ENUMS.rule_hit,
                '.'.join([exploration.id, state.id,
                          state_models.DEFAULT_RULE_SPEC_REPR])
            )
            default_count = stats_models.Journal.get_value_count_by_id(event_id)
            journal = stats_models.Journal.get(event_id, strict=False)
            top_default_answers = collections.Counter(
                journal.values).most_common(5) if journal else []

            # Count the number of times an answer was submitted, regardless
            # of which rule it hits.
            completed_count = 0
            for handler in state.widget.handlers:
                for rule in handler.rule_specs:
                    rule_name = str(rule)
                    event_id = get_event_id(
                        STATS_ENUMS.rule_hit, '%s.%s.%s' %
                        (exploration.id, state.id, rule_name))
                    completed_count += (
                        stats_models.Journal.get_value_count_by_id(event_id))

            incomplete_count = all_count - completed_count

            state_rank, improve_type = 0, ''

            eligible_flags = []
            default_rule = filter(
                lambda rule: str(rule) == state_models.DEFAULT_RULE_SPEC_REPR,
                state.widget.handlers[0].rule_specs
            )[0]
            default_self_loop = default_rule.dest == state.id
            if float(default_count) / all_count > .2 and default_self_loop:
                eligible_flags.append({
                    'rank': default_count,
                    'improve_type': IMPROVE_TYPE_DEFAULT})
            if float(incomplete_count) / all_count > .2:
                eligible_flags.append({
                    'rank': incomplete_count,
                    'improve_type': IMPROVE_TYPE_INCOMPLETE})

            # TODO(sll): Break this method out into smaller, more testable
            # parts; then remove the following commented code.
            """
            j_arr = [j.id for j in stats_models.Journal.get_all()]
            raise Exception('%s %s %s %s %s %s' % (
                default_count, incomplete_count, all_count, completed_count,
                eligible_flags, j_arr
            ))
            """

            eligible_flags = sorted(
                eligible_flags, key=lambda flag: flag['rank'], reverse=True)
            if eligible_flags:
                state_rank = eligible_flags[0]['rank']
                improve_type = eligible_flags[0]['improve_type']

            ranked_states.append({
                'exp_id': exploration.id,
                'exp_name': exploration.title,
                'state_id': state.id,
                'state_name': state.name,
                'rank': state_rank,
                'type': improve_type,
                'top_default_answers': top_default_answers
            })

    problem_states = sorted(
        [state for state in ranked_states if state['rank'] != 0],
        key=lambda state: state['rank'],
        reverse=True)
    return problem_states[:10]


def delete_all_stats():
    """Deletes all statistics."""
    stats_models.Counter.delete_all()
    stats_models.Journal.delete_all()
    stats_models.Tally.delete_all()
