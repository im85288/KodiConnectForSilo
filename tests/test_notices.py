from resources.lib.silokodi import notices


def test_a_new_next_up_episode_reads_as_silos_own_notice():
    data = {'type': 'episode.available', 'series_id': 'show-1', 'episode_id': 'ep-9', 'series_title': 'Slow Horses',
            'season_number': 5, 'episode_number': 3, 'episode_title': 'Missing'}
    assert notices.text(data) == ('Slow Horses', 'New episode · S05E03 · Missing')
    assert notices.picture_id(data) == 'show-1'


def test_a_placeholder_episode_title_is_left_out():
    data = {'type': 'episode.available', 'series_title': 'Vigil', 'season_number': 2, 'episode_number': 1,
            'episode_title': 'TBA'}
    assert notices.text(data) == ('Vigil', 'New episode · S02E01')
    data['episode_title'] = 'Episode 1'
    assert notices.text(data) == ('Vigil', 'New episode · S02E01')


def test_arrivals_and_request_answers():
    assert notices.text({'type': 'request.fulfilled', 'series_title': 'Dune: Part Two'}) == (
        'Dune: Part Two is now available', 'In your library now')
    assert notices.text({'type': 'watchlist.available', 'series_title': 'Andor'})[0] == 'Andor is now available'
    assert notices.text({'type': 'request.approved', 'reason_flags': {'title': 'Severance'}}) == (
        'Severance was approved', 'Your request was approved')
    assert notices.text({'type': 'request.declined', 'reason_flags': {'title': 'Cats', 'reason': 'No.'}}) == (
        'Cats was declined', 'Reason: No.')


def test_admin_notices_are_not_shown():
    assert notices.text({'type': 'webhook.auto_disabled'}) is None
    assert notices.text({}) is None
