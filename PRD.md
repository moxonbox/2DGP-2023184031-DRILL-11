
- 목표: 상태 클래스에 따른 Boy 클래스 객체 이동 및 스프라이트 애니메이션
- 언어: Python 및 pico2d, transitions 라이브러리 및 이외 필요한 요소
- 대상: main.py , Boy.py


- 상태 종류: idle, sleep, slow_walk, walk, run, jump, auto run
- 유의 사항: 각 상태는 상태 클래스.
- idle: 정지 상태에서 스프라이트만 변화, 상태 시작 후 5초 뒤 sleep 상태 전환
- sleep: y=40 위치에서 캐릭터가 눕도록 배치.
- slow_walk: walk 상태에서 이속 감소, idle 스프라이트 사용
- walk: S / D 입력시 캐릭터 좌 / 우 이동
- run: walk 상태에서 이속 증가.
- jump: 캐릭터 점프 (이동 중에도 가능)
- autorun: A키 입력시 상태 진입, idle 또는 sleep에서 진입하면 바라보는 방향의 run 상태를 기준으로 실행, 나머지는 입력된 상태를 계속 유지, 이동 시에는 이속 증가 및 캐릭터 크기 확대,  이동 중 뷰포트 경계에 닿으면 방향 전환, 시작 5초 경과 후 입력이 없으면 idle 상태로 전환, autorun 상태에서 다른 상태 키 입력시 autorun 중지 및 해당 상태로 전환
