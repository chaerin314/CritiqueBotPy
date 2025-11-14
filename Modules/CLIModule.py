class CLIModule:
    def __init__(self, critic_module, evaluation_module=None):
        self.cm = critic_module
        self.em = evaluation_module

    def run(self):
        init = True
        history = []
        while True:
            if init:
                history = []
                ipt = input("당신의 주장:").strip()
                init = False
            else:
                print("\n다음 중 선택하세요:")
                print("1) 지금 봇의 반박에 다시 반박하기")
                print("2) 이 주장/반박에 대한 평가·코칭 받기")
                print("3) 새로운 주장으로 다시 시작하기")
                print("4) 종료하기")
                choice = input("번호: ").strip()
                if choice == "1":
                    ipt = input("당신의 재반박:").strip()
                elif choice == "2":
                    print("Not implemented yet.")
                    continue
                elif choice == "3":
                    init = True
                    continue
                elif choice == "4":
                    break
                else:
                    print("Invalid input: ", choice)
                    continue

            history.append({"role": "user", "content": ipt})
            rsp = self.cm.call(history)  # {"txt": str, "ref": dict[str,str]}
            history.append({"role": "assistant", "content": rsp["txt"]})

            print("\n🤖 봇의 반박:")
            print(rsp["txt"])

            refs = rsp.get("ref") or {}
            if refs:
                print("\n🔗 참조 링크:")
                for title, url in refs.items():
                    print(f"- {title}: {url}")
