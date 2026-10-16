"""Evaluación real del modelo integrado; no consulta catálogos ni simula que sean resultados reales."""
import json
from pathlib import Path
import sys
from time import monotonic
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_ai import LocalAI
from intelligence import PLAN_PROMPT,PLAN_SCHEMA,RANK_PROMPT,RANK_SCHEMA

CASES=[
 ('chill','Quiero un modpack tranquilo para un PC malillo, construir y pelear con algún jefe que otro pero no mucho más.'),
 ('negative','Quiero construir casas y decorar sin jefes, sin magia ni maquinaria. Quiero optimización.'),
 ('factory','Quiero fábricas, automatización, electricidad y máquinas, con mucho contenido. Sin magia.')]
CATEGORIES=['Adventure and RPG','Magic','Technology','World Gen','Mobs','Structures','Utility & QoL',
            'Storage','Food','Farming','Cosmetic','Performance']


def main():
    ai=LocalAI();reports=[]
    with ai.session():
        for name,phrase in CASES:
            start=monotonic()
            plan=ai.complete(PLAN_PROMPT,{'description':phrase,'categories':CATEGORIES},PLAN_SCHEMA)
            queries={q for g in plan['goals'] for q in g['queries']}
            if name=='chill':
                assert queries & {'building blocks','building tools','furniture','decoration'},plan
                assert queries & {'summon boss','bosses'},plan
                assert not queries & {'invasions','horror'},plan
            if name=='negative':
                assert not queries & {'bosses','summon boss','magic','spells','machines','industrial'},plan
            if name=='factory':
                assert queries & {'automation','industrial','factory','machines','electricity'},plan
                assert not queries & {'magic','spells'},plan
            report={'case':name,'seconds':round(monotonic()-start,1),'plan':plan}
            reports.append(report);print(json.dumps(report,ensure_ascii=False),flush=True)
        brief={'summary':'Construir a tu ritmo con un jefe invocable ocasional y rendimiento para PC modesto.',
               'pace':'Tranquilo','combat':'Elegible','performance':'Prioritario','exclusions':['Magia','Invasiones'],'goals':[],'assumptions':[]}
        cards=[
            {'id':10,'title':'FerriteCore','summary':'Memory usage optimizations','categories':['Performance']},
            {'id':20,'title':'Building Wands','summary':'Building wands with different placement modes','categories':['Utility & QoL']},
            {'id':30,'title':'Meet Your Fight','summary':'Bosses do not come on their own; craft a summoning item to call each boss.','categories':['Adventure and RPG']},
            {'id':40,'title':'Performance HUD (fixture)','summary':'Displays an FPS and RAM overlay. Does not optimize the game.','categories':['Utility & QoL']},
            {'id':50,'title':'Nightly Invasion (fixture)','summary':'Forces hostile invasions every night and prevents peaceful building.','categories':['Mobs']},
            {'id':60,'title':'Magic Expansion (fixture)','summary':'Adds a full spellcasting progression and magic dimensions.','categories':['Magic']}]
        result=ai.complete(RANK_PROMPT,{'experience':brief,'cards':cards},RANK_SCHEMA)
        selected={e['id'] for e in result['selected'] if e['score']>=65}
        assert {10,20,30}<=selected,result
        assert not {40,50,60}&selected,result
        reports.append({'case':'curation','result':result})
        print(json.dumps(reports[-1],ensure_ascii=False),flush=True)
    Path('/tmp/smapt-ai-report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2))
    print('Evaluación real completada.',flush=True)

if __name__=='__main__':main()
