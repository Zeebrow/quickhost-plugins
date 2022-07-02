#import json
#from pathlib import Path
#import os
#
#tgt_data_dir = os.environ['QH_TEST_DATA_DIR']
#
#if tgt_data_dir is None:
#    print(f"env var 'QH_TEST_DATA_DIR' is unset! ")
#    exit()
#
#data_dir = Path(tgt_data_dir) / 'mock-data'
#if not data_dir.exists():
#    data_dir.mkdir()
#
def store_test_data(resource: str, action: str, response_data: dict):
    pass
#def store_test_data(resource: str, action: str, response_data: dict):
#    if type(response_data) != type({}):
#        print(f"!!!! could not record response data: response_data was type '{type(response_data)}', expected 'dict'.")
#        return False
#    d = Path(data_dir) / resource 
#    if not d.exists():
#        d.mkdir()
#    fp = d / f"{action}.json"
#    with fp.open("a") as f:
#        f.writelines(json.dumps(response_data, indent=2))
#    return True
#    
#    
#
#if __name__ == '__main__':
#    store_test_data(resource='blabla', action='test', response_data={'data':'True'})
#
#    @get_test_data
#    def asdf(a):
#        print(f'asdf: {a}')
#        return
#    asdf('asddfasdfasdf')
#
#    class A:
#        def dostuff():
#            print('doin stuff')
#            return
#        
