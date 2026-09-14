"""External behavioral checker for authored maintenance scenarios; never an agent input."""
import importlib
import json
from pathlib import Path
import sys


def raises(exception, call):
    try: call()
    except exception: return
    raise AssertionError(f'expected {exception.__name__}')


def check(project, stage):
    root=Path.cwd();sys.path.insert(0,str(root/'src' if (root/'src').is_dir() else root))
    module={'boltons':'boltons.strutils','more-itertools':'more_itertools',
            'packaging':'packaging.utils','itsdangerous':'itsdangerous.timed'}[project]
    m=importlib.import_module(module)
    assert Path(m.__file__).resolve().is_relative_to(root.resolve()),'must use local source'

    def compatibility():
        if project=='boltons':
            assert m.slugify('Beyoncé Foo')=='beyoncé_foo'
            assert m.slugify('Beyoncé Foo',ascii=True)==b'beyonce_foo'
            assert m.slugify('A B',delim='',lower=False)=='AB'
            assert m.camel2under('FooBar')=='foo_bar'
        elif project=='more-itertools':
            assert list(m.chunked(range(3),2))==[[0,1],[2]]
            raises(ValueError,lambda:list(m.chunked(range(3),2,strict=True)))
            assert list(m.sliced([0,1,2],2))==[[0,1],[2]]
        elif project=='packaging':
            assert m.canonicalize_version('1.0.0')=='1'
            assert m.canonicalize_version('invalid version')=='invalid version'
            assert m.canonicalize_version('1.0.0',strip_trailing_zero=False)=='1.0.0'
            assert m.canonicalize_name('Foo_Bar')=='foo-bar'
        else:
            from itsdangerous import BadSignature, SignatureExpired
            serializer,token,clock=timed_fixture(m)
            clock[0]=4000
            assert serializer.loads(token)=={'id':7}
            raises(SignatureExpired,lambda:serializer.loads(token,max_age=60))
            raises(BadSignature,lambda:serializer.loads(token+'x'))

    def feature():
        if project=='boltons':
            expected='beyonce-foo' if stage<3 else 'beyoncé.foo'
            assert m.filename_slug('Beyoncé Foo')==expected
            assert m.filename_slug('Beyoncé Foo',delimiter='',ascii=False)=='beyoncéfoo'
            assert m.filename_slug('Beyoncé Foo',delimiter=':',ascii=True)=='beyonce:foo'
            assert m.filename_slug('')==''
            if stage>=2:
                assert m.legacy_slug('Beyoncé Foo')=='beyoncé_foo'
                assert m.legacy_slug('Beyoncé Foo',delimiter=':',ascii=True)=='beyonce:foo'
            if stage==3:
                assert m.filename_slugs(iter(['Beyoncé Foo','A B']))==['beyoncé.foo','a.b']
                assert m.filename_slugs(['A B'],delimiter='',ascii=False)==['ab']
        elif project=='more-itertools':
            if stage<3: raises(ValueError,lambda:list(m.strict_chunked(iter(range(3)),2)))
            else: assert list(m.strict_chunked(iter(range(3)),2))==[[0,1],[2]]
            assert list(m.strict_chunked(iter(range(3)),2,strict=False))==[[0,1],[2]]
            raises(ValueError,lambda:list(m.strict_chunked(range(3),2,strict=True)))
            raises(ValueError,lambda:list(m.strict_chunked([1],0)))
            consumed=[]
            def source():
                for x in range(5): consumed.append(x);yield x
            chunks=iter(m.strict_chunked(source(),2,strict=False))
            assert next(chunks)==[0,1] and consumed==[0,1]
            if stage>=2:
                assert list(m.compatible_chunked(range(3),2))==[[0,1],[2]]
                raises(ValueError,lambda:list(m.compatible_chunked(range(3),2,strict=True)))
            if stage==3:
                assert m.strict_chunked_map(iter([range(3),range(2)]),2)==[[[0,1],[2]],[[0,1]]]
                raises(ValueError,lambda:m.strict_chunked_map([range(3)],2,strict=True))
        elif project=='packaging':
            from packaging.version import InvalidVersion,Version
            assert m.project_version('1.0.0')==('1.0.0' if stage<3 else '1')
            assert m.project_version(Version('2.0.0'),strip_trailing_zero=False)=='2.0.0'
            assert m.project_version('2.0.0',strip_trailing_zero=True)=='2'
            raises(InvalidVersion,lambda:m.project_version('invalid version'))
            if stage>=2:
                assert m.compat_version('1.0.0')=='1'
                assert m.compat_version('invalid version')=='invalid version'
                assert m.compat_version('1.0.0',strip_trailing_zero=False)=='1.0.0'
            if stage==3:
                assert m.project_versions(iter(['1.0.0',Version('2.0.0')]))==['1','2']
                assert m.project_versions(['1.0.0'],strip_trailing_zero=False)==['1.0.0']
                raises(InvalidVersion,lambda:m.project_versions(['invalid version']))
        else:
            from itsdangerous import BadSignature,SignatureExpired
            serializer,token,clock=timed_fixture(m)
            limit=60 if stage<3 else 120
            clock[0]=limit
            assert m.loads_session(serializer,token)=={'id':7}
            clock[0]=limit+1
            raises(SignatureExpired,lambda:m.loads_session(serializer,token))
            assert m.loads_session(serializer,token,max_age=3600)=={'id':7}
            clock[0]=1
            raises(SignatureExpired,lambda:m.loads_session(serializer,token,max_age=0))
            raises(BadSignature,lambda:m.loads_session(serializer,token+'x'))
            if stage>=2:
                clock[0]=121
                assert m.loads_legacy(serializer,token)=={'id':7}
                raises(SignatureExpired,lambda:m.loads_legacy(serializer,token,max_age=0))
            if stage==3:
                clock[0]=61
                assert m.loads_sessions(serializer,iter([token,token]))==[{'id':7},{'id':7}]
                raises(BadSignature,lambda:m.loads_sessions(serializer,[token+'x']))
    result={}
    for name,operation in [('compatibility',compatibility),('feature',feature)]:
        try: operation();result[name]={'pass':True}
        except Exception as error: result[name]={'pass':False,'error':f'{type(error).__name__}: {error}'}
    return result


def timed_fixture(m):
    clock=[0]
    class ClockSigner(m.TimestampSigner):
        def get_timestamp(self): return clock[0]
    serializer=m.TimedSerializer('test-only-secret',signer=ClockSigner)
    return serializer,serializer.dumps({'id':7}),clock


if __name__=='__main__':
    try: result=check(sys.argv[1],int(sys.argv[2]))
    except Exception as error:
        result={'compatibility':{'pass':False,'error':repr(error)},'feature':{'pass':False}}
    print(json.dumps(result))
    raise SystemExit(2 if not result['compatibility']['pass'] else 0 if result['feature']['pass'] else 1)
