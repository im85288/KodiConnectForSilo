# -*- coding: utf-8 -*-
"""Kodi's picture cache sized for 4K menus (advancedsettings.xml): only
imageres, fanartres and the scaling method change, never lower, and what was
there before goes back."""
from resources.lib.silokodi import bigart

USERS = '''<advancedsettings version="1.0">
  <cache>
    <memorysize>139460608</memorysize>
  </cache>
  <imageres>2160</imageres>
  <imagescalingalgorithm>bicubic</imagescalingalgorithm>
</advancedsettings>
'''


def test_only_what_is_smaller_or_missing_is_wanted():
    assert bigart.wanted('') == {'imageres': '1440', 'fanartres': '2160', 'imagescalingalgorithm': 'lanczos'}
    # A larger poster size and a chosen scaling method stay as the user set them.
    assert bigart.wanted(USERS) == {'fanartres': '2160'}
    assert bigart.wanted('<advancedsettings><imageres>720</imageres><fanartres>2160</fanartres>'
                         '<imagescalingalgorithm>lanczos</imagescalingalgorithm></advancedsettings>') == {'imageres': '1440'}


def test_values_are_merged_and_the_rest_kept():
    out = bigart.with_values(USERS, bigart.wanted(USERS))
    assert '<memorysize>139460608</memorysize>' in out and '<imageres>2160</imageres>' in out
    assert '<fanartres>2160</fanartres>' in out and '<imagescalingalgorithm>bicubic</imagescalingalgorithm>' in out
    assert out.rstrip().endswith('</advancedsettings>') and bigart.COMMENT in out
    fresh = bigart.with_values('', bigart.wanted(''))
    assert fresh.startswith('<advancedsettings version="1.0">') and '<imageres>1440</imageres>' in fresh


def test_a_file_in_another_form_is_left_alone():
    assert bigart.usable('') and bigart.usable(USERS)
    assert not bigart.usable('<settings><imageres>720</imageres></settings>')
    assert not bigart.usable('<advancedsettings>')  # broken


def test_apply_then_revert_gives_the_file_back(tmp_path, monkeypatch):
    target = tmp_path / 'advancedsettings.xml'
    target.write_text(USERS, encoding='utf-8')
    saved = {}
    monkeypatch.setattr(bigart, 'path', lambda: str(target))
    monkeypatch.setattr(bigart.kodi, 'setting', lambda key: saved.get(key, ''))
    monkeypatch.setattr(bigart.kodi, 'set_setting', saved.__setitem__)
    assert bigart.apply() is True
    assert '<fanartres>2160</fanartres>' in target.read_text(encoding='utf-8')
    assert (tmp_path / 'advancedsettings.xml.before-kodiconnectforsilo').read_text(encoding='utf-8') == USERS
    assert bigart.apply() is False  # nothing left to raise
    assert bigart.revert() is True
    assert target.read_text(encoding='utf-8') == USERS
    assert bigart.revert() is False and not bigart.changed()


def test_no_file_before_means_none_after(tmp_path, monkeypatch):
    target = tmp_path / 'advancedsettings.xml'
    saved = {}
    monkeypatch.setattr(bigart, 'path', lambda: str(target))
    monkeypatch.setattr(bigart.kodi, 'setting', lambda key: saved.get(key, ''))
    monkeypatch.setattr(bigart.kodi, 'set_setting', saved.__setitem__)
    assert bigart.apply() is True and '<imageres>1440</imageres>' in target.read_text(encoding='utf-8')
    assert bigart.revert() is True
    left = target.read_text(encoding='utf-8')
    assert 'imageres' not in left and 'fanartres' not in left and bigart.COMMENT not in left


def test_the_question_is_asked_once_per_menu_size(tmp_path, monkeypatch):
    target = tmp_path / 'advancedsettings.xml'
    saved, asked = {}, []
    monkeypatch.setattr(bigart, 'path', lambda: str(target))
    monkeypatch.setattr(bigart.kodi, 'setting', lambda key: saved.get(key, ''))
    monkeypatch.setattr(bigart.kodi, 'set_setting', saved.__setitem__)
    monkeypatch.setattr(bigart.kodi, 'string', lambda string_id: str(string_id))
    monkeypatch.setattr(bigart.xbmc, 'getCondVisibility', lambda condition: False)

    class Dialog(object):
        def yesno(self, heading, text):
            asked.append(text)
            return text != '30245'  # yes to the sizes, no to restarting now
    monkeypatch.setattr(bigart.xbmcgui, 'Dialog', Dialog)
    bigart.check(True)
    assert asked == ['30242', '30245'] and '<fanartres>2160</fanartres>' in target.read_text(encoding='utf-8')
    bigart.check(True)
    assert len(asked) == 2  # not again
    bigart.check(False)  # 4K menus off: offered back
    assert asked[2] == '30243' and 'fanartres' not in target.read_text(encoding='utf-8')
