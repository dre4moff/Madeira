"""Production touch view lifetime/input under lightweight UIKit test doubles.
Verifies delivery and cancellation, not rendered UIKit/Metal performance.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'app/Madeira/TouchGamepad.swift').read_text()
pure = source[source.index('struct GamepadSample:'):source.index('// MARK: - UIKit touch lifetime')]
view = source[source.index('final class TouchPadView:'):]
stubs = r'''
import Foundation
import CoreGraphics
final class UIColor { static let white=UIColor(), clear=UIColor(); func withAlphaComponent(_ a: CGFloat)->UIColor { self } }
struct UIFont { enum Style { case caption1 }; static func preferredFont(forTextStyle: Style)->Self { Self() } }
final class Layer { var cornerRadius: CGFloat=0 }
@MainActor class UIView: NSObject {
    init(frame: CGRect) { super.init(); self.frame = frame }
    override convenience init() { self.init(frame: .zero) }
    required init?(coder: NSCoder) { super.init() }
    var frame=CGRect.zero, bounds=CGRect.zero, center=CGPoint.zero
    var backgroundColor: UIColor?, isMultipleTouchEnabled=false, isUserInteractionEnabled=true, isHidden=false
    var window: UIWindow?, layer=Layer(), subviews: [UIView]=[]
    func addSubview(_ v: UIView) { subviews.append(v) }
    func layoutSubviews() {}; func didMoveToWindow() {}
    func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {}
    func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {}
    func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent?) {}
    func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent?) {}
}
@MainActor final class UILabel: UIView {
    enum Alignment { case center }; var textAlignment=Alignment.center
    var font=UIFont(), textColor: UIColor?, text: String?
}
@MainActor final class UIWindow: UIView {}
@MainActor final class UITouch: NSObject { var point=CGPoint.zero; func location(in view: UIView)->CGPoint { point } }
final class UIEvent: NSObject {}
@MainActor final class UIApplication {
    enum State { case active, inactive }; var applicationState=State.active
    static let shared=UIApplication()
    static let willResignActiveNotification=Notification.Name("synthetic.resign")
}
enum CATransaction { static func begin() {}; static func setDisableActions(_ b: Bool) {}; static func commit() {} }
@MainActor final class GamepadInput {
    static let shared=GamepadInput(); var state=TouchGamepadState(), delivered=0
    func touch(owner: UUID, control: UUID, value: GamepadSample?) { delivered += 1; state.update(owner: owner, control: control, value: value) }
}
'''
fixture = r'''
@main struct Check {
    @MainActor static func main() {
        let id=UUID(), v=TouchPadView(), f=UITouch(), second=UITouch()
        let input=GamepadInput.shared; input.state.configure([id])
        v.bounds=CGRect(x:0,y:0,width:200,height:200); v.layoutSubviews()
        var publications=0
        v.configure(control:id,action:"LS") { _,_ in publications += 1 }
        f.point=CGPoint(x:100,y:100); v.touchesBegan([f],with:nil)
        for i in 0..<10000 {
            f.point=CGPoint(x:100+Double(i%70),y:100)
            v.touchesMoved([f],with:nil)
        }
        assert(input.delivered==10001 && publications==0 && input.state.sample.lx>0)
        assert(v.subviews[0].center.x>100) // knob moved without publishing SwiftUI state
        v.touchesCancelled([f],with:nil)
        assert(input.state.sample==GamepadSample() && publications==1)
        v.configure(control:id,action:"A") { _,_ in publications += 1 }
        v.touchesBegan([f,second],with:nil); assert(input.state.sample.buttons==0x1000)
        v.touchesEnded([f],with:nil); assert(input.state.sample.buttons==0x1000)
        v.touchesEnded([second],with:nil); assert(input.state.sample==GamepadSample())
        v.touchesBegan([f],with:nil)
        NotificationCenter.default.post(name:UIApplication.willResignActiveNotification,object:nil)
        assert(input.state.sample==GamepadSample())
        v.configure(control:id,action:"RS") { _,_ in publications += 1 }
        v.touchesBegan([f],with:nil); f.point.x += 50; v.touchesMoved([f],with:nil)
        assert(input.state.sample.rx>0)
        v.bounds.size.width=240; v.layoutSubviews(); assert(input.state.sample==GamepadSample())
        v.touchesBegan([f],with:nil); v.configure(control:id,action:"B") { _,_ in publications += 1 }
        assert(input.state.sample==GamepadSample())
        v.touchesBegan([f],with:nil); v.window=nil; v.didMoveToWindow()
        assert(input.state.sample==GamepadSample())
        UIApplication.shared.applicationState = .inactive
        v.touchesBegan([f],with:nil); assert(input.state.sample==GamepadSample())
        print("PASS: 10000 analog moves delivered without SwiftUI publications; multi-touch holds, cancellation, inactive app, resize, remap and window removal release correctly")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-touch-feedback-') as folder:
    p = Path(folder)
    (p / 'Check.swift').write_text(stubs + pure + view + fixture)
    subprocess.run(['xcrun', 'swiftc', '-swift-version', '5', '-parse-as-library', '-sanitize=address',
                    str(p / 'Check.swift'), '-o', str(p / 'check')], check=True)
    subprocess.run([str(p / 'check')], check=True)
