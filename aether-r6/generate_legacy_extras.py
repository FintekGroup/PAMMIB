from pathlib import Path
import generate_eas as base

ROOT=Path(__file__).resolve().parent
MT4=ROOT/"mt4"; MT5=ROOT/"mt5"

def render_zebers_mq4():
    s=dict(magic=3310,dd=12.0,start=2,end=16,tp=40,sl=28,be=False,be_trig=20,trail=False,trail_start=20,trail_step=5)
    return f'''// Aether Quantus - Zebers Modernized R6
// Separate modernization proposal; not represented as untouched Zebers 1.0.
#property strict
#property version "6.10"
string StrategyName="Zebers Modernized R6";
{base.common_inputs(s)}
input double FixedLot=0.02;
input int FastMAPeriod=6;
input int SlowMAPeriod=20;
input double QuickRangePips=20.0;
double gLot=0.02;
''' + base.MQL4_COMMON + r'''
bool ApplyProfile(){
   gMaxDD=MaxDrawdownPercent; gTrailStart=TrailStartPips; gTrailStep=TrailStepPips;
   if(RiskProfile!="Conservative" && RiskProfile!="Moderate" && RiskProfile!="Aggressive") return false;
   gLot=FixedLot; return true;
}
int OnInit(){ if(!ApplyProfile()) return INIT_PARAMETERS_INCORRECT; return INIT_SUCCEEDED; }
void OnDeinit(const int reason){ Comment(""); }
void OnTick(){
   ManageStops(); UpdateHUD("Zebers modernization proposal");
   if(!EntryGate()) return;
   if(CountOpen(-1)>0) return;
   double range=(iHigh(Symbol(),Period(),1)-iLow(Symbol(),Period(),1))/PipSize();
   if(range>=QuickRangePips) return;
   double f=iMA(Symbol(),Period(),FastMAPeriod,0,MODE_EMA,PRICE_CLOSE,0);
   double s=iMA(Symbol(),Period(),SlowMAPeriod,0,MODE_EMA,PRICE_CLOSE,0);
   if(f>s) SafeSend(OP_BUY,gLot,"Zebers Buy");
   else if(f<s) SafeSend(OP_SELL,gLot,"Zebers Sell");
}
'''

def render_zebers_mq5():
    s=dict(magic=3310,dd=12.0,start=2,end=16,tp=40,sl=28,be=False,be_trig=20,trail=False,trail_start=20,trail_step=5)
    return f'''// Aether Quantus - Zebers Modernized R6 MT5
// Separate modernization proposal; not represented as untouched Zebers 1.0.
#property strict
#property version "6.10"
string StrategyName="Zebers Modernized R6 MT5";
{base.common_inputs(s)}
input double FixedLot=0.02;
input int FastMAPeriod=6;
input int SlowMAPeriod=20;
input double QuickRangePips=20.0;
double gLot=0.02; int hFast=INVALID_HANDLE,hSlow=INVALID_HANDLE;
''' + base.MQL5_COMMON + r'''
bool ApplyProfile(){
   gMaxDD=MaxDrawdownPercent; gTrailStart=TrailStartPips; gTrailStep=TrailStepPips;
   if(RiskProfile!="Conservative" && RiskProfile!="Moderate" && RiskProfile!="Aggressive") return false;
   gLot=FixedLot; return true;
}
int OnInit(){
   if(!ApplyProfile()) return INIT_PARAMETERS_INCORRECT;
   hFast=iMA(_Symbol,PERIOD_CURRENT,FastMAPeriod,0,MODE_EMA,PRICE_CLOSE);
   hSlow=iMA(_Symbol,PERIOD_CURRENT,SlowMAPeriod,0,MODE_EMA,PRICE_CLOSE);
   if(hFast==INVALID_HANDLE || hSlow==INVALID_HANDLE) return INIT_FAILED;
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){ if(hFast!=INVALID_HANDLE) IndicatorRelease(hFast); if(hSlow!=INVALID_HANDLE) IndicatorRelease(hSlow); Comment(""); }
void OnTick(){
   ManageStops(); UpdateHUD("Zebers modernization proposal");
   if(!EntryGate() || CountOpen(-1)>0) return;
   double range=(iHigh(_Symbol,PERIOD_CURRENT,1)-iLow(_Symbol,PERIOD_CURRENT,1))/PipSize();
   if(range>=QuickRangePips) return;
   double f=0.0,s=0.0;
   if(!BufferValue(hFast,0,f) || !BufferValue(hSlow,0,s)) return;
   if(f>s) SafeSend(ORDER_TYPE_BUY,gLot,"Zebers Buy");
   else if(f<s) SafeSend(ORDER_TYPE_SELL,gLot,"Zebers Sell");
}
'''

def render_ringer_mq4():
    s=dict(magic=6291,dd=13.0,start=2,end=17,tp=35,sl=33,be=True,be_trig=15,trail=True,trail_start=14,trail_step=5)
    return f'''// Aether Quantus - TraideRinger Modernized R6
// Four-lane modernization proposal. Original TraideRinger identity requires separate source reconciliation.
#property strict
#property version "6.10"
string StrategyName="TraideRinger Modernized R6";
{base.common_inputs(s)}
input int MAPeriod=20;
input int KPeriod=3;
input int DPeriod=10;
input int Slowing=3;
input int StochOB=80;
input int StochOS=20;
input int StochTrendCap=65;
input bool UseTrendEntries=true;
input bool UseCounterEntries=true;
input double FixedLot=0.02;
input double Marti=1.30;
input int LevelMax=6;
input double RangePips=18.0;
input double RangeMult=1.25;
double gBaseLot=0.02,gMarti=1.30; int gLevelMax=6;
''' + base.MQL4_COMMON + r'''
string LaneTag(int lane){ if(lane==0)return "BUY TREND"; if(lane==1)return "SELL TREND"; if(lane==2)return "BUY COUNTER"; return "SELL COUNTER"; }
bool IsBuyLane(int lane){ return (lane==0 || lane==2); }
int CountLane(int lane){
   int c=0; string tag=LaneTag(lane);
   for(int i=OrdersTotal()-1;i>=0;i--){
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderSymbol()!=Symbol() || OrderMagicNumber()!=MagicNumber) continue;
      if(OrderType()!=OP_BUY && OrderType()!=OP_SELL) continue;
      if(StringFind(OrderComment(),tag,0)==0) c++;
   }
   return c;
}
double LastLanePrice(int lane){
   datetime best=0; double p=0.0; string tag=LaneTag(lane);
   for(int i=OrdersTotal()-1;i>=0;i--){
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderSymbol()!=Symbol() || OrderMagicNumber()!=MagicNumber) continue;
      if(StringFind(OrderComment(),tag,0)!=0) continue;
      if(OrderOpenTime()>=best){best=OrderOpenTime();p=OrderOpenPrice();}
   }
   return p;
}
double LaneStep(int count){ return RangePips*MathPow(RangeMult,count); }
bool LaneSpacingOK(int lane,int count){
   double last=LastLanePrice(lane); if(last<=0) return false; RefreshRates();
   if(IsBuyLane(lane)) return ((last-Bid)/PipSize()>=LaneStep(count));
   return ((Ask-last)/PipSize()>=LaneStep(count));
}
double MA1(){ return iMA(Symbol(),Period(),MAPeriod,0,MODE_LWMA,PRICE_CLOSE,1); }
double ST1(){ return iStochastic(Symbol(),Period(),KPeriod,DPeriod,Slowing,MODE_SMA,0,MODE_MAIN,1); }
bool LaneSignal(int lane){
   double c=iClose(Symbol(),Period(),1),ma=MA1(),st=ST1();
   if(lane==0) return UseTrendEntries && c>ma && st<StochTrendCap;
   if(lane==1) return UseTrendEntries && c<ma && st>(100-StochTrendCap);
   if(lane==2) return UseCounterEntries && c<ma && st<=StochOS;
   return UseCounterEntries && c>ma && st>=StochOB;
}
void TryLane(int lane){
   int n=CountLane(lane); int type=(IsBuyLane(lane)?OP_BUY:OP_SELL);
   if(n==0){
      if(LaneSignal(lane)) SafeSend(type,gBaseLot,LaneTag(lane)+"-Lvl-0");
   } else if(n<gLevelMax && LaneSpacingOK(lane,n)){
      SafeSend(type,gBaseLot*MathPow(gMarti,n),LaneTag(lane)+"-Lvl-"+IntegerToString(n));
   }
}
bool ApplyProfile(){
   gMaxDD=MaxDrawdownPercent; gTrailStart=TrailStartPips; gTrailStep=TrailStepPips;
   if(RiskProfile=="Conservative"){gBaseLot=FixedLot;gMarti=MathMax(Marti,1.20);gLevelMax=MathMin(LevelMax,8);}
   else if(RiskProfile=="Moderate"){gBaseLot=MathMax(FixedLot,0.03);gMarti=MathMax(Marti,1.30);gLevelMax=MathMin(LevelMax,10);}
   else if(RiskProfile=="Aggressive"){gBaseLot=MathMax(FixedLot,0.05);gMarti=MathMax(Marti,1.45);gLevelMax=MathMin(LevelMax,12);}
   else return false;
   return true;
}
int OnInit(){ if(!ApplyProfile()) return INIT_PARAMETERS_INCORRECT; return INIT_SUCCEEDED; }
void OnDeinit(const int reason){ Comment(""); }
void OnTick(){
   ManageStops(); UpdateHUD("BT:"+IntegerToString(CountLane(0))+" ST:"+IntegerToString(CountLane(1))+" BC:"+IntegerToString(CountLane(2))+" SC:"+IntegerToString(CountLane(3)));
   if(!EntryGate()) return;
   TryLane(0); TryLane(1); TryLane(2); TryLane(3);
}
'''

def render_ringer_mq5():
    s=dict(magic=6291,dd=13.0,start=2,end=17,tp=35,sl=33,be=True,be_trig=15,trail=True,trail_start=14,trail_step=5)
    return f'''// Aether Quantus - TraideRinger Modernized R6 MT5
// Four-lane modernization proposal. Original TraideRinger identity requires separate source reconciliation.
#property strict
#property version "6.10"
string StrategyName="TraideRinger Modernized R6 MT5";
{base.common_inputs(s)}
input bool RequireHedging=true;
input int MAPeriod=20;
input int KPeriod=3;
input int DPeriod=10;
input int Slowing=3;
input int StochOB=80;
input int StochOS=20;
input int StochTrendCap=65;
input bool UseTrendEntries=true;
input bool UseCounterEntries=true;
input double FixedLot=0.02;
input double Marti=1.30;
input int LevelMax=6;
input double RangePips=18.0;
input double RangeMult=1.25;
double gBaseLot=0.02,gMarti=1.30; int gLevelMax=6,hMA=INVALID_HANDLE,hST=INVALID_HANDLE;
''' + base.MQL5_COMMON + r'''
string LaneTag(int lane){ if(lane==0)return "BUY TREND"; if(lane==1)return "SELL TREND"; if(lane==2)return "BUY COUNTER"; return "SELL COUNTER"; }
bool IsBuyLane(int lane){ return (lane==0 || lane==2); }
int CountLane(int lane){
   int c=0; string tag=LaneTag(lane);
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong ticket=PositionGetTicket(i); if(!OwnPosition(ticket)) continue;
      string cm=PositionGetString(POSITION_COMMENT);
      if(StringFind(cm,tag,0)==0) c++;
   }
   return c;
}
double LastLanePrice(int lane){
   datetime best=0; double p=0.0; string tag=LaneTag(lane);
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong ticket=PositionGetTicket(i); if(!OwnPosition(ticket)) continue;
      string cm=PositionGetString(POSITION_COMMENT); if(StringFind(cm,tag,0)!=0) continue;
      datetime tm=(datetime)PositionGetInteger(POSITION_TIME);
      if(tm>=best){best=tm;p=PositionGetDouble(POSITION_PRICE_OPEN);}
   }
   return p;
}
double LaneStep(int count){ return RangePips*MathPow(RangeMult,count); }
bool LaneSpacingOK(int lane,int count){
   double last=LastLanePrice(lane); if(last<=0) return false; MqlTick q; if(!TickNow(q)) return false;
   if(IsBuyLane(lane)) return ((last-q.bid)/PipSize()>=LaneStep(count));
   return ((q.ask-last)/PipSize()>=LaneStep(count));
}
bool LaneSignal(int lane){
   double ma=0.0,st=0.0; if(!BufferValue(hMA,1,ma) || !BufferValue(hST,1,st)) return false;
   double c=iClose(_Symbol,PERIOD_CURRENT,1);
   if(lane==0) return UseTrendEntries && c>ma && st<StochTrendCap;
   if(lane==1) return UseTrendEntries && c<ma && st>(100-StochTrendCap);
   if(lane==2) return UseCounterEntries && c<ma && st<=StochOS;
   return UseCounterEntries && c>ma && st>=StochOB;
}
void TryLane(int lane){
   int n=CountLane(lane); ENUM_ORDER_TYPE type=(IsBuyLane(lane)?ORDER_TYPE_BUY:ORDER_TYPE_SELL);
   if(n==0){
      if(LaneSignal(lane)) SafeSend(type,gBaseLot,LaneTag(lane)+"-Lvl-0");
   } else if(n<gLevelMax && LaneSpacingOK(lane,n)){
      SafeSend(type,gBaseLot*MathPow(gMarti,n),LaneTag(lane)+"-Lvl-"+IntegerToString(n));
   }
}
bool ApplyProfile(){
   gMaxDD=MaxDrawdownPercent; gTrailStart=TrailStartPips; gTrailStep=TrailStepPips;
   if(RiskProfile=="Conservative"){gBaseLot=FixedLot;gMarti=MathMax(Marti,1.20);gLevelMax=MathMin(LevelMax,8);}
   else if(RiskProfile=="Moderate"){gBaseLot=MathMax(FixedLot,0.03);gMarti=MathMax(Marti,1.30);gLevelMax=MathMin(LevelMax,10);}
   else if(RiskProfile=="Aggressive"){gBaseLot=MathMax(FixedLot,0.05);gMarti=MathMax(Marti,1.45);gLevelMax=MathMin(LevelMax,12);}
   else return false;
   return true;
}
int OnInit(){
   if(!ApplyProfile()) return INIT_PARAMETERS_INCORRECT;
   if(RequireHedging && AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return INIT_FAILED;
   hMA=iMA(_Symbol,PERIOD_CURRENT,MAPeriod,0,MODE_LWMA,PRICE_CLOSE);
   hST=iStochastic(_Symbol,PERIOD_CURRENT,KPeriod,DPeriod,Slowing,MODE_SMA,STO_LOWHIGH);
   if(hMA==INVALID_HANDLE || hST==INVALID_HANDLE) return INIT_FAILED;
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){ if(hMA!=INVALID_HANDLE) IndicatorRelease(hMA); if(hST!=INVALID_HANDLE) IndicatorRelease(hST); Comment(""); }
void OnTick(){
   ManageStops(); UpdateHUD("BT:"+IntegerToString(CountLane(0))+" ST:"+IntegerToString(CountLane(1))+" BC:"+IntegerToString(CountLane(2))+" SC:"+IntegerToString(CountLane(3)));
   if(!EntryGate()) return;
   TryLane(0); TryLane(1); TryLane(2); TryLane(3);
}
'''

(MT4/"Zebers_Modernized_R6.mq4").write_text(render_zebers_mq4(),encoding="utf-8")
(MT5/"Zebers_Modernized_R6.mq5").write_text(render_zebers_mq5(),encoding="utf-8")
(MT4/"TraideRinger_Modernized_R6.mq4").write_text(render_ringer_mq4(),encoding="utf-8")
(MT5/"TraideRinger_Modernized_R6.mq5").write_text(render_ringer_mq5(),encoding="utf-8")
print("generated supplemental TraideRinger + Zebers MT4/MT5 candidates")
