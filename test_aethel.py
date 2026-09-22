from ai_engine import AethelInference, KnowledgeRouter

brain = AethelInference()

assert 'Oi!' in brain.reply('oi')[0]
assert brain.reply('quanto é 25*4')[0] == 'Resultado: 100'
roblox, meta = brain.reply('crie um script para Roblox Studio que faça sprint ao apertar Shift')
assert meta['language'] == 'Luau'
assert 'LeftShift' in roblox and 'StarterPlayerScripts' in roblox
leader, _ = brain.reply('faça um leaderboard de coins no Roblox Studio')
assert 'leaderstats' in leader and 'Coins' in leader
assert 'def main' in brain.reply('me ajude com Python')[0]
print('AETHEL TESTS: OK')
