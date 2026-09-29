from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parent
MT4 = ROOT / "mt4"
MT5 = ROOT / "mt5"
MT4.mkdir(parents=True, exist_ok=True)
MT5.mkdir(parents=True, exist_ok=True)

# R6 production candidates are deliberately separate from the preserved R5.6/R2 baselines.
# They retain each 4.1 strategy's core signal/direction while applying execution/accounting fixes.

STRATS = [
    dict(key="GearboxAIX", name="Gearbox AIX R6", magic=6810, dd=13.0, start=1, end=18,
         tp=30, sl=35, be=False, be_trig=15, trail=True, trail_start=15, trail_step=5, kind="gearbox"),
    dict(key="KingRobot", name="King Robot R6", magic=4210, dd=12.0, start=1, end=17,
         tp=75, sl=50, be=True, be_trig=20, trail=True, trail_start=30, trail_step=20, kind="king"),
    dict(key="TradeExplorer", name="TradeExplorer R6", magic=5120, dd=15.0, start=2, end=17,
         tp=40, sl=25, be=True, be_trig=15, trail=True, trail_start=15, trail_step=5, kind="tradeexplorer"),
    dict(key="Bolt", name="Bolt R6", magic=3210, dd=12.0, start=2, end=16,
         tp=50, sl=30, be=True, be_trig=20, trail=True, trail_start=15, trail_step=5, kind="bolt"),
    dict(key="StrikeZone", name="StrikeZone R6", magic=3213, dd=14.0, start=2, end=16,
         tp=30, sl=28, be=False, be_trig=15, trail=True, trail_start=12, trail_step=4, kind="strike"),
    dict(key="StrikeZonePlus", name="StrikeZone Plus R6", magic=3214, dd=16.0, start=2, end=16,
         tp=35, sl=30, be=False, be_trig=15, trail=True, trail_start=14, trail_step=5, kind="strikeplus"),
    dict(key="StealthGrid", name="Stealth Grid R6", magic=3250, dd=10.0, start=1, end=18,
         tp=18, sl=70, be=False, be_trig=20, trail=True, trail_start=15, trail_step=4, kind="stealth"),
    dict(key="GhostRinger", name="GhostRinger R6", magic=6290, dd=13.0, start=2, end=17,
         tp=35, sl=33, be=False, be_trig=14, trail=True, trail_start=14, trail_step=5, kind="ghost"),
    dict(key="ChronoPulse", name="ChronoPulse R6", magic=7778, dd=15.0, start=2, end=17,
         tp=30, sl=25, be=False, be_trig=15, trail=True, trail_start=15, trail_step=3, kind="chrono"),
]

def b(v): return "true" if v else "false"

MQL4_COMMON = r'''
double gMaxDD=0.0, gTrailStart=0.0, gTrailStep=0.0;
datetime gLastEntryBar=0;

double PipSize(){ return ((Digits==3 || Digits==5) ? 10.0*Point : Point); }
double PipsToPrice(double p){ return p*PipSize(); }
double SpreadPips(){ RefreshRates(); double p=PipSize(); if(p<=0) return 999999.0; return (Ask-Bid)/p; }
bool TradeActionsAllowed(){ return (IsTesting() || AllowLiveTrading); }

bool SessionAllowed(){
   if(!UseSessionFilter) return true;
   int h=TimeHour(TimeCurrent());
   if(StartHour==EndHour) return true;
   if(StartHour<EndHour) return (h>=StartHour && h<EndHour);
   return (h>=StartHour || h<EndHour);
}
double FloatingDDPercent(){
   double b=AccountBalance(), e=AccountEquity();
   if(b<=0.0) return 0.0;
   return MathMax(0.0,(b-e)/b*100.0);
}
bool EntryGate(){
   if(!TradeActionsAllowed()) return false;
   if(UseEquityGuard && AccountBalance()>0.0 && AccountEquity()<AccountBalance()*(1.0-gMaxDD/100.0)) return false;
   if(!SessionAllowed()) return false;
   if(UseSpreadFilter && SpreadPips()>MaxSpreadPips) return false;
   return true;
}
double NormalizeVolume(double lots){
   double mn=MarketInfo(Symbol(),MODE_MINLOT), mx=MarketInfo(Symbol(),MODE_MAXLOT), st=MarketInfo(Symbol(),MODE_LOTSTEP);
   if(mn<=0) mn=0.01; if(mx<=0) mx=100.0; if(st<=0) st=0.01;
   lots=MathMax(mn,MathMin(mx,lots));
   lots=MathFloor(lots/st+1e-9)*st;
   return NormalizeDouble(lots,8);
}
int CountOpen(int type){
   int n=0;
   for(int i=OrdersTotal()-1;i>=0;i--){
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderSymbol()!=Symbol() || OrderMagicNumber()!=MagicNumber) continue;
      if(OrderType()!=OP_BUY && OrderType()!=OP_SELL) continue;
      if(type>=0 && OrderType()!=type) continue;
      n++;
   }
   return n;
}
double LatestOpenPrice(int type){
   datetime best=0; double price=0.0;
   for(int i=OrdersTotal()-1;i>=0;i--){
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderSymbol()!=Symbol() || OrderMagicNumber()!=MagicNumber || OrderType()!=type) continue;
      if(OrderOpenTime()>=best){ best=OrderOpenTime(); price=OrderOpenPrice(); }
   }
   return price;
}
double LatestLots(int type){
   datetime best=0; double lots=0.0;
   for(int i=OrdersTotal()-1;i>=0;i--){
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderSymbol()!=Symbol() || OrderMagicNumber()!=MagicNumber || OrderType()!=type) continue;
      if(OrderOpenTime()>=best){ best=OrderOpenTime(); lots=OrderLots(); }
   }
   return lots;
}
double MinStopDistance(){
   double a=MarketInfo(Symbol(),MODE_STOPLEVEL), f=MarketInfo(Symbol(),MODE_FREEZELEVEL);
   return MathMax(a,f)*Point;
}
bool TransientTradeError(int e){ return (e==4 || e==6 || e==8 || e==129 || e==136 || e==137 || e==138 || e==146); }

int SafeSend(int type,double lots,string cmt){
   if(!TradeActionsAllowed()) return -1;
   lots=NormalizeVolume(lots);
   for(int attempt=0;attempt<3;attempt++){
      while(IsTradeContextBusy() && !IsStopped()) Sleep(20);
      RefreshRates();
      if(UseSpreadFilter && SpreadPips()>MaxSpreadPips) return -1;
      double px=(type==OP_BUY ? Ask : Bid);
      double fm=AccountFreeMarginCheck(Symbol(),type,lots);
      if(fm<=0.0){ Print(StrategyName,": margin check rejected volume ",DoubleToString(lots,4)); return -1; }
      double sl=0.0,tp=0.0,md=MinStopDistance();
      if(UseStopLoss){
         sl=(type==OP_BUY ? px-PipsToPrice(StopLossPips) : px+PipsToPrice(StopLossPips));
         if(type==OP_BUY && px-sl<md) sl=px-md;
         if(type==OP_SELL && sl-px<md) sl=px+md;
         sl=NormalizeDouble(sl,Digits);
      }
      if(UseTakeProfit){
         tp=(type==OP_BUY ? px+PipsToPrice(TakeProfitPips) : px-PipsToPrice(TakeProfitPips));
         if(type==OP_BUY && tp-px<md) tp=px+md;
         if(type==OP_SELL && px-tp<md) tp=px-md;
         tp=NormalizeDouble(tp,Digits);
      }
      ResetLastError();
      int ticket=OrderSend(Symbol(),type,lots,NormalizeDouble(px,Digits),Slippage,sl,tp,cmt,MagicNumber,0,(type==OP_BUY?clrGreen:clrRed));
      if(ticket>=0){ gLastEntryBar=iTime(Symbol(),Period(),0); return ticket; }
      int e=GetLastError();
      Print(StrategyName,": OrderSend failed attempt=",attempt+1," err=",e);
      if(!TransientTradeError(e)) break;
      Sleep(150);
   }
   return -1;
}
bool SafeModifyStop(int ticket,double requested){
   if(!TradeActionsAllowed()) return false;
   if(!OrderSelect(ticket,SELECT_BY_TICKET,MODE_TRADES)) return false;
   int type=OrderType(); if(type!=OP_BUY && type!=OP_SELL) return false;
   RefreshRates();
   double md=MinStopDistance();
   double sl=requested;
   if(type==OP_BUY) sl=MathMin(sl,Bid-md);
   else sl=MathMax(sl,Ask+md);
   sl=NormalizeDouble(sl,Digits);
   double old=OrderStopLoss();
   if(type==OP_BUY && old>0.0 && sl<=old+Point/2.0) return false;
   if(type==OP_SELL && old>0.0 && sl>=old-Point/2.0) return false;
   if(type==OP_BUY && sl>=Bid) return false;
   if(type==OP_SELL && sl<=Ask) return false;
   ResetLastError();
   bool ok=OrderModify(ticket,OrderOpenPrice(),sl,OrderTakeProfit(),0,clrYellow);
   if(!ok) Print(StrategyName,": OrderModify failed ticket=",ticket," err=",GetLastError());
   return ok;
}
bool SafeClose(int ticket){
   if(!TradeActionsAllowed()) return false;
   if(!OrderSelect(ticket,SELECT_BY_TICKET,MODE_TRADES)) return false;
   int type=OrderType(); if(type!=OP_BUY && type!=OP_SELL) return false;
   RefreshRates();
   double px=(type==OP_BUY?Bid:Ask);
   ResetLastError();
   bool ok=OrderClose(ticket,OrderLots(),px,Slippage,clrRed);
   if(!ok) Print(StrategyName,": OrderClose failed ticket=",ticket," err=",GetLastError());
   return ok;
}
void ManageStops(){
   if(!TradeActionsAllowed()) return;
   RefreshRates();
   for(int i=OrdersTotal()-1;i>=0;i--){
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderSymbol()!=Symbol() || OrderMagicNumber()!=MagicNumber) continue;
      int type=OrderType(); if(type!=OP_BUY && type!=OP_SELL) continue;
      double op=OrderOpenPrice();
      double pp=(type==OP_BUY ? (Bid-op)/PipSize() : (op-Ask)/PipSize());
      int ticket=OrderTicket();
      if(UseBreakeven && pp>=BreakevenTriggerPips){
         double be=(type==OP_BUY ? op+PipsToPrice(1.0) : op-PipsToPrice(1.0));
         SafeModifyStop(ticket,be);
         if(!OrderSelect(ticket,SELECT_BY_TICKET,MODE_TRADES)) continue;
      }
      if(UseTrailingStop && pp>=gTrailStart){
         double ts=(type==OP_BUY ? Bid-PipsToPrice(gTrailStep) : Ask+PipsToPrice(gTrailStep));
         SafeModifyStop(ticket,ts);
      }
   }
}
bool NewBar(){
   static datetime last=0;
   datetime cur=iTime(Symbol(),Period(),0);
   if(cur>0 && cur!=last){ last=cur; return true; }
   return false;
}
void UpdateHUD(string extra){
   string mode=(IsTesting()?"TEST":(AllowLiveTrading?"LIVE":"LIVE-LOCKED"));
   string guard=(UseEquityGuard && FloatingDDPercent()>=gMaxDD ? "GUARD" : "OK");
   Comment(StrategyName,"\nProfile: ",RiskProfile," | ",mode," | ",guard,
           "\nSpread: ",DoubleToString(SpreadPips(),1)," pips | Open: ",CountOpen(-1),
           "\nBalance: ",DoubleToString(AccountBalance(),2)," | Equity: ",DoubleToString(AccountEquity(),2),
           " | DD: ",DoubleToString(FloatingDDPercent(),2),"%",
           "\n",extra);
}
'''

MQL5_COMMON = r'''
double gMaxDD=0.0, gTrailStart=0.0, gTrailStep=0.0;
datetime gLastEntryBar=0;

double PointSize(){ double v=0.0; SymbolInfoDouble(_Symbol,SYMBOL_POINT,v); return v; }
int SymDigits(){ long d=0; SymbolInfoInteger(_Symbol,SYMBOL_DIGITS,d); return (int)d; }
double PipSize(){ int d=SymDigits(); double p=PointSize(); return ((d==3 || d==5)?10.0*p:p); }
double PipsToPrice(double p){ return p*PipSize(); }
bool TickNow(MqlTick &t){ return SymbolInfoTick(_Symbol,t); }
double SpreadPips(){ MqlTick t; if(!TickNow(t) || PipSize()<=0) return 999999.0; return (t.ask-t.bid)/PipSize(); }
bool TradeActionsAllowed(){ return (MQLInfoInteger(MQL_TESTER) || AllowLiveTrading); }

bool SessionAllowed(){
   if(!UseSessionFilter) return true;
   MqlDateTime dt; TimeToStruct(TimeCurrent(),dt); int h=dt.hour;
   if(StartHour==EndHour) return true;
   if(StartHour<EndHour) return (h>=StartHour && h<EndHour);
   return (h>=StartHour || h<EndHour);
}
double FloatingDDPercent(){
   double b=AccountInfoDouble(ACCOUNT_BALANCE), e=AccountInfoDouble(ACCOUNT_EQUITY);
   if(b<=0.0) return 0.0;
   return MathMax(0.0,(b-e)/b*100.0);
}
bool EntryGate(){
   if(!TradeActionsAllowed()) return false;
   double b=AccountInfoDouble(ACCOUNT_BALANCE),e=AccountInfoDouble(ACCOUNT_EQUITY);
   if(UseEquityGuard && b>0.0 && e<b*(1.0-gMaxDD/100.0)) return false;
   if(!SessionAllowed()) return false;
   if(UseSpreadFilter && SpreadPips()>MaxSpreadPips) return false;
   return true;
}
double NormalizeVolume(double lots){
   double mn=0.01,mx=100.0,st=0.01;
   SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN,mn); SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX,mx); SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP,st);
   if(st<=0) st=0.01; lots=MathMax(mn,MathMin(mx,lots));
   lots=MathFloor(lots/st+1e-9)*st;
   return NormalizeDouble(lots,8);
}
bool OwnPosition(ulong ticket,long typeFilter=-1){
   if(ticket==0 || !PositionSelectByTicket(ticket)) return false;
   if(PositionGetString(POSITION_SYMBOL)!=_Symbol) return false;
   if((long)PositionGetInteger(POSITION_MAGIC)!=(long)MagicNumber) return false;
   long t=PositionGetInteger(POSITION_TYPE);
   if(typeFilter>=0 && t!=typeFilter) return false;
   return true;
}
int CountOpen(long typeFilter=-1){
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong ticket=PositionGetTicket(i);
      if(OwnPosition(ticket,typeFilter)) n++;
   }
   return n;
}
double LatestOpenPrice(long type){
   datetime best=0; double price=0.0;
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong ticket=PositionGetTicket(i); if(!OwnPosition(ticket,type)) continue;
      datetime tm=(datetime)PositionGetInteger(POSITION_TIME);
      if(tm>=best){ best=tm; price=PositionGetDouble(POSITION_PRICE_OPEN); }
   }
   return price;
}
double LatestLots(long type){
   datetime best=0; double lots=0.0;
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong ticket=PositionGetTicket(i); if(!OwnPosition(ticket,type)) continue;
      datetime tm=(datetime)PositionGetInteger(POSITION_TIME);
      if(tm>=best){ best=tm; lots=PositionGetDouble(POSITION_VOLUME); }
   }
   return lots;
}
double MinStopDistance(){
   long a=0,f=0; SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL,a); SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL,f);
   return (double)MathMax(a,f)*PointSize();
}
ENUM_ORDER_TYPE_FILLING FillMode(){
   long mode=0; SymbolInfoInteger(_Symbol,SYMBOL_FILLING_MODE,mode);
   if((mode & SYMBOL_FILLING_FOK)==SYMBOL_FILLING_FOK) return ORDER_FILLING_FOK;
   if((mode & SYMBOL_FILLING_IOC)==SYMBOL_FILLING_IOC) return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
}
bool TradeResultOK(uint rc){
   return (rc==TRADE_RETCODE_DONE || rc==TRADE_RETCODE_PLACED || rc==TRADE_RETCODE_DONE_PARTIAL);
}
ulong SafeSend(ENUM_ORDER_TYPE type,double lots,string cmt){
   if(!TradeActionsAllowed()) return 0;
   lots=NormalizeVolume(lots);
   for(int attempt=0;attempt<3;attempt++){
      MqlTick t; if(!TickNow(t)) return 0;
      if(UseSpreadFilter && SpreadPips()>MaxSpreadPips) return 0;
      double px=(type==ORDER_TYPE_BUY?t.ask:t.bid), margin=0.0;
      if(!OrderCalcMargin(type,_Symbol,lots,px,margin) || margin>AccountInfoDouble(ACCOUNT_MARGIN_FREE)){
         Print(StrategyName,": margin check rejected volume ",DoubleToString(lots,4)); return 0;
      }
      double sl=0.0,tp=0.0,md=MinStopDistance(); int dg=SymDigits();
      if(UseStopLoss){
         sl=(type==ORDER_TYPE_BUY?px-PipsToPrice(StopLossPips):px+PipsToPrice(StopLossPips));
         if(type==ORDER_TYPE_BUY && px-sl<md) sl=px-md;
         if(type==ORDER_TYPE_SELL && sl-px<md) sl=px+md;
         sl=NormalizeDouble(sl,dg);
      }
      if(UseTakeProfit){
         tp=(type==ORDER_TYPE_BUY?px+PipsToPrice(TakeProfitPips):px-PipsToPrice(TakeProfitPips));
         if(type==ORDER_TYPE_BUY && tp-px<md) tp=px+md;
         if(type==ORDER_TYPE_SELL && px-tp<md) tp=px-md;
         tp=NormalizeDouble(tp,dg);
      }
      MqlTradeRequest req={}; MqlTradeResult res={};
      req.action=TRADE_ACTION_DEAL; req.symbol=_Symbol; req.volume=lots; req.type=type; req.price=NormalizeDouble(px,dg);
      req.sl=sl; req.tp=tp; req.deviation=(ulong)Slippage; req.magic=(ulong)MagicNumber; req.comment=cmt;
      req.type_time=ORDER_TIME_GTC; req.type_filling=FillMode();
      ResetLastError();
      if(OrderSend(req,res) && TradeResultOK(res.retcode)){ gLastEntryBar=iTime(_Symbol,PERIOD_CURRENT,0); return (res.order>0?res.order:res.deal); }
      Print(StrategyName,": OrderSend attempt=",attempt+1," retcode=",res.retcode," err=",GetLastError());
      Sleep(150);
   }
   return 0;
}
bool SafeModifyStop(ulong ticket,double requested){
   if(!TradeActionsAllowed() || !OwnPosition(ticket)) return false;
   long pt=PositionGetInteger(POSITION_TYPE); MqlTick t; if(!TickNow(t)) return false;
   double md=MinStopDistance(),sl=requested,old=PositionGetDouble(POSITION_SL),tp=PositionGetDouble(POSITION_TP);
   if(pt==POSITION_TYPE_BUY) sl=MathMin(sl,t.bid-md); else sl=MathMax(sl,t.ask+md);
   sl=NormalizeDouble(sl,SymDigits());
   if(pt==POSITION_TYPE_BUY && old>0.0 && sl<=old+PointSize()/2.0) return false;
   if(pt==POSITION_TYPE_SELL && old>0.0 && sl>=old-PointSize()/2.0) return false;
   MqlTradeRequest req={}; MqlTradeResult res={};
   req.action=TRADE_ACTION_SLTP; req.symbol=_Symbol; req.position=ticket; req.magic=(ulong)MagicNumber; req.sl=sl; req.tp=tp;
   if(!OrderSend(req,res) || !TradeResultOK(res.retcode)){ Print(StrategyName,": modify failed ",res.retcode); return false; }
   return true;
}
bool SafeClose(ulong ticket){
   if(!TradeActionsAllowed() || !OwnPosition(ticket)) return false;
   long pt=PositionGetInteger(POSITION_TYPE); double vol=PositionGetDouble(POSITION_VOLUME); MqlTick t; if(!TickNow(t)) return false;
   ENUM_ORDER_TYPE ot=(pt==POSITION_TYPE_BUY?ORDER_TYPE_SELL:ORDER_TYPE_BUY); double px=(ot==ORDER_TYPE_BUY?t.ask:t.bid);
   MqlTradeRequest req={}; MqlTradeResult res={};
   req.action=TRADE_ACTION_DEAL; req.symbol=_Symbol; req.position=ticket; req.volume=vol; req.type=ot; req.price=NormalizeDouble(px,SymDigits());
   req.deviation=(ulong)Slippage; req.magic=(ulong)MagicNumber; req.comment=StrategyName+" close"; req.type_filling=FillMode();
   if(!OrderSend(req,res) || !TradeResultOK(res.retcode)){ Print(StrategyName,": close failed ",res.retcode); return false; }
   return true;
}
void ManageStops(){
   if(!TradeActionsAllowed()) return;
   MqlTick t; if(!TickNow(t)) return;
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong ticket=PositionGetTicket(i); if(!OwnPosition(ticket)) continue;
      long pt=PositionGetInteger(POSITION_TYPE); double op=PositionGetDouble(POSITION_PRICE_OPEN);
      double pp=(pt==POSITION_TYPE_BUY?(t.bid-op)/PipSize():(op-t.ask)/PipSize());
      if(UseBreakeven && pp>=BreakevenTriggerPips){
         double be=(pt==POSITION_TYPE_BUY?op+PipsToPrice(1.0):op-PipsToPrice(1.0));
         SafeModifyStop(ticket,be);
      }
      if(UseTrailingStop && pp>=gTrailStart){
         if(!OwnPosition(ticket)) continue;
         double ts=(pt==POSITION_TYPE_BUY?t.bid-PipsToPrice(gTrailStep):t.ask+PipsToPrice(gTrailStep));
         SafeModifyStop(ticket,ts);
      }
   }
}
bool NewBar(){
   static datetime last=0; datetime cur=iTime(_Symbol,PERIOD_CURRENT,0);
   if(cur>0 && cur!=last){ last=cur; return true; } return false;
}
bool BufferValue(int handle,int shift,double &v){
   if(handle==INVALID_HANDLE) return false;
   double a[1]; if(CopyBuffer(handle,0,shift,1,a)!=1) return false; v=a[0]; return true;
}
void UpdateHUD(string extra){
   string mode=(MQLInfoInteger(MQL_TESTER)?"TEST":(AllowLiveTrading?"LIVE":"LIVE-LOCKED"));
   string guard=(UseEquityGuard && FloatingDDPercent()>=gMaxDD?"GUARD":"OK");
   Comment(StrategyName,"\nProfile: ",RiskProfile," | ",mode," | ",guard,
           "\nSpread: ",DoubleToString(SpreadPips(),1)," pips | Open: ",CountOpen(-1),
           "\nBalance: ",DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE),2)," | Equity: ",DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY),2),
           " | DD: ",DoubleToString(FloatingDDPercent(),2),"%",
           "\n",extra);
}
'''

def common_inputs(s):
    return f'''input string RiskProfile="Conservative";
input bool AllowLiveTrading=false;
input int MagicNumber={s["magic"]};
input int Slippage=3;
input bool UseEquityGuard=true;
input double MaxDrawdownPercent={s["dd"]};
input bool UseSessionFilter=true;
input int StartHour={s["start"]};
input int EndHour={s["end"]};
input bool UseSpreadFilter=true;
input double MaxSpreadPips=2.0;
input bool UseTakeProfit=true;
input double TakeProfitPips={s["tp"]};
input bool UseStopLoss=true;
input double StopLossPips={s["sl"]};
input bool UseBreakeven={b(s["be"])};
input double BreakevenTriggerPips={s["be_trig"]};
input bool UseTrailingStop={b(s["trail"])};
input double TrailStartPips={s["trail_start"]};
input double TrailStepPips={s["trail_step"]};
'''

def strategy_parts(kind, lang):
    buy = "OP_BUY" if lang=="m4" else "POSITION_TYPE_BUY"
    sell = "OP_SELL" if lang=="m4" else "POSITION_TYPE_SELL"
    oby = "OP_BUY" if lang=="m4" else "ORDER_TYPE_BUY"
    osl = "OP_SELL" if lang=="m4" else "ORDER_TYPE_SELL"
    sym = "Symbol()" if lang=="m4" else "_Symbol"
    per = "Period()" if lang=="m4" else "PERIOD_CURRENT"

    if kind=="gearbox":
        extra='''input int MaxGridTrades=6;
input double GridStepPips=28.0;
input bool AdverseOnly=false; // false preserves the 4.1 absolute-spacing behavior
double gLot=0.02,gGridMult=1.45; int gRecoveryType=0;
'''
        profile='''if(RiskProfile=="Conservative"){gLot=0.02;gGridMult=1.45;gRecoveryType=0;}
else if(RiskProfile=="Moderate"){gLot=0.05;gGridMult=1.60;gRecoveryType=1;}
else if(RiskProfile=="Aggressive"){gLot=0.12;gGridMult=1.80;gRecoveryType=1;}
else return false;'''
        tick=f'''int n=CountOpen({buy});
if(n==0) SafeSend({oby},gLot,"AIX Grid 1");
else if(n<MaxGridTrades){{
   double last=LatestOpenPrice({buy});
   bool spacing=(last>0.0 && MathAbs(({"Bid" if lang=="m4" else "SymbolInfoDouble(_Symbol,SYMBOL_BID)"}-last)/PipSize())>=GridStepPips);
   if(AdverseOnly && last>0.0) spacing=((last-{"Bid" if lang=="m4" else "SymbolInfoDouble(_Symbol,SYMBOL_BID)"})/PipSize()>=GridStepPips);
   if(spacing){{
      double prev=LatestLots({buy});
      double lot=(gRecoveryType==1?gLot*MathPow(gGridMult,n):prev*gGridMult);
      SafeSend({oby},lot,"AIX Grid");
   }}
}}'''
        return extra,profile,"",tick,"", ""

    if kind=="king":
        extra='''input bool OneEntryPerBar=false;
double gLot=0.02; int gRecovery=1,gMaxTrades=3;
'''
        profile='''if(RiskProfile=="Conservative"){gLot=0.02;gRecovery=1;gMaxTrades=3;gMaxDD=12.0;}
else if(RiskProfile=="Moderate"){gLot=0.04;gRecovery=2;gMaxTrades=5;gMaxDD=18.0;}
else if(RiskProfile=="Aggressive"){gLot=0.08;gRecovery=3;gMaxTrades=7;gMaxDD=25.0;}
else return false;'''
        tick=f'''int n=CountOpen({buy});
if(n<gMaxTrades){{
   bool timing=(!OneEntryPerBar || gLastEntryBar!=iTime({sym},{per},0));
   if(timing) SafeSend({oby},gLot*MathPow((double)gRecovery,n),"KR Entry");
}}'''
        return extra,profile,"",tick,"", ""

    if kind=="tradeexplorer":
        extra='''input bool UseGhostSkip=true;
input double GhostPipThreshold=10.0;
double gLot=0.02; int gFast=5,gSlow=21,gGhostCount=2;
'''
        profile='''if(RiskProfile=="Conservative"){gLot=0.02;gFast=5;gSlow=21;gGhostCount=2;}
else if(RiskProfile=="Moderate"){gLot=0.05;gFast=4;gSlow=15;gGhostCount=3;}
else if(RiskProfile=="Aggressive"){gLot=0.10;gFast=3;gSlow=10;gGhostCount=5;}
else return false;'''
        if lang=="m4":
            helpers='''bool GhostCheck(int direction){
   if(!UseGhostSkip) return true;
   for(int i=1;i<=gGhostCount;i++){
      double o=iOpen(Symbol(),Period(),i),c=iClose(Symbol(),Period(),i);
      double move=(c-o)/PipSize();
      if(direction==OP_BUY && move<=GhostPipThreshold) return false;
      if(direction==OP_SELL && -move<=GhostPipThreshold) return false;
   }
   return true;
}'''
            tick='''if(CountOpen(-1)==0){
   double f=iMA(Symbol(),Period(),gFast,0,MODE_EMA,PRICE_CLOSE,0);
   double s=iMA(Symbol(),Period(),gSlow,0,MODE_EMA,PRICE_CLOSE,0);
   if(f>s && GhostCheck(OP_BUY)) SafeSend(OP_BUY,gLot,"TE Buy");
   else if(f<s && GhostCheck(OP_SELL)) SafeSend(OP_SELL,gLot,"TE Sell");
}'''
            init=""
            deinit=""
        else:
            helpers='''int hFast=INVALID_HANDLE,hSlow=INVALID_HANDLE;
bool GhostCheck(long direction){
   if(!UseGhostSkip) return true;
   for(int i=1;i<=gGhostCount;i++){
      double o=iOpen(_Symbol,PERIOD_CURRENT,i),c=iClose(_Symbol,PERIOD_CURRENT,i);
      double move=(c-o)/PipSize();
      if(direction==POSITION_TYPE_BUY && move<=GhostPipThreshold) return false;
      if(direction==POSITION_TYPE_SELL && -move<=GhostPipThreshold) return false;
   }
   return true;
}'''
            init='''hFast=iMA(_Symbol,PERIOD_CURRENT,gFast,0,MODE_EMA,PRICE_CLOSE);
hSlow=iMA(_Symbol,PERIOD_CURRENT,gSlow,0,MODE_EMA,PRICE_CLOSE);
if(hFast==INVALID_HANDLE || hSlow==INVALID_HANDLE) return INIT_FAILED;'''
            deinit='''if(hFast!=INVALID_HANDLE) IndicatorRelease(hFast);
if(hSlow!=INVALID_HANDLE) IndicatorRelease(hSlow);'''
            tick='''if(CountOpen(-1)==0){
   double f=0.0,s=0.0;
   if(BufferValue(hFast,0,f) && BufferValue(hSlow,0,s)){
      if(f>s && GhostCheck(POSITION_TYPE_BUY)) SafeSend(ORDER_TYPE_BUY,gLot,"TE Buy");
      else if(f<s && GhostCheck(POSITION_TYPE_SELL)) SafeSend(ORDER_TYPE_SELL,gLot,"TE Sell");
   }
}'''
        return extra,profile,helpers,tick,init,deinit

    if kind=="bolt":
        extra='''double gLot=0.02; int gFast=5,gSlow=20; double gRange=15.0;
'''
        profile='''if(RiskProfile=="Conservative"){gLot=0.02;gFast=5;gSlow=20;gRange=15.0;gMaxDD=12.0;}
else if(RiskProfile=="Moderate"){gLot=0.05;gFast=4;gSlow=18;gRange=12.0;gMaxDD=20.0;}
else if(RiskProfile=="Aggressive"){gLot=0.10;gFast=3;gSlow=15;gRange=10.0;gMaxDD=30.0;}
else return false;'''
        if lang=="m4":
            tick='''if(CountOpen(-1)==0){
   double range=(iHigh(Symbol(),Period(),1)-iLow(Symbol(),Period(),1))/PipSize();
   if(range<gRange){
      double f=iMA(Symbol(),Period(),gFast,0,MODE_EMA,PRICE_CLOSE,0);
      double s=iMA(Symbol(),Period(),gSlow,0,MODE_EMA,PRICE_CLOSE,0);
      RefreshRates();
      if(f>s && Bid>s) SafeSend(OP_BUY,gLot,"Bolt Buy");
      else if(f<s && Ask<s) SafeSend(OP_SELL,gLot,"Bolt Sell");
   }
}'''
            helpers=init=deinit=""
        else:
            helpers='''int hFast=INVALID_HANDLE,hSlow=INVALID_HANDLE;'''
            init='''hFast=iMA(_Symbol,PERIOD_CURRENT,gFast,0,MODE_EMA,PRICE_CLOSE);
hSlow=iMA(_Symbol,PERIOD_CURRENT,gSlow,0,MODE_EMA,PRICE_CLOSE);
if(hFast==INVALID_HANDLE || hSlow==INVALID_HANDLE) return INIT_FAILED;'''
            deinit='''if(hFast!=INVALID_HANDLE) IndicatorRelease(hFast);
if(hSlow!=INVALID_HANDLE) IndicatorRelease(hSlow);'''
            tick='''if(CountOpen(-1)==0){
   double range=(iHigh(_Symbol,PERIOD_CURRENT,1)-iLow(_Symbol,PERIOD_CURRENT,1))/PipSize();
   if(range<gRange){
      double f=0.0,s=0.0; MqlTick q;
      if(BufferValue(hFast,0,f) && BufferValue(hSlow,0,s) && TickNow(q)){
         if(f>s && q.bid>s) SafeSend(ORDER_TYPE_BUY,gLot,"Bolt Buy");
         else if(f<s && q.ask<s) SafeSend(ORDER_TYPE_SELL,gLot,"Bolt Sell");
      }
   }
}'''
        return extra,profile,helpers,tick,init,deinit

    if kind=="strike":
        extra='''input int ATRPeriod=14;
input double ATRMult=1.8;
double gLot=0.02;
'''
        profile='''if(RiskProfile=="Conservative") gLot=0.02;
else if(RiskProfile=="Moderate") gLot=0.06;
else if(RiskProfile=="Aggressive") gLot=0.15;
else return false;'''
        if lang=="m4":
            tick='''if(CountOpen(-1)==0){
   double atr=iATR(Symbol(),Period(),ATRPeriod,0);
   double fb=iLow(Symbol(),Period(),1)-ATRMult*atr, fs=iHigh(Symbol(),Period(),1)+ATRMult*atr;
   RefreshRates();
   if(Bid<fb) SafeSend(OP_BUY,gLot,"SZ Fade Buy");
   else if(Ask>fs) SafeSend(OP_SELL,gLot,"SZ Fade Sell");
}'''
            helpers=init=deinit=""
        else:
            helpers='''int hATR=INVALID_HANDLE;'''
            init='''hATR=iATR(_Symbol,PERIOD_CURRENT,ATRPeriod); if(hATR==INVALID_HANDLE) return INIT_FAILED;'''
            deinit='''if(hATR!=INVALID_HANDLE) IndicatorRelease(hATR);'''
            tick='''if(CountOpen(-1)==0){
   double atr=0.0; MqlTick q;
   if(BufferValue(hATR,0,atr) && TickNow(q)){
      double fb=iLow(_Symbol,PERIOD_CURRENT,1)-ATRMult*atr, fs=iHigh(_Symbol,PERIOD_CURRENT,1)+ATRMult*atr;
      if(q.bid<fb) SafeSend(ORDER_TYPE_BUY,gLot,"SZ Fade Buy");
      else if(q.ask>fs) SafeSend(ORDER_TYPE_SELL,gLot,"SZ Fade Sell");
   }
}'''
        return extra,profile,helpers,tick,init,deinit

    if kind=="strikeplus":
        extra='''input int ATRPeriod=14;
input double ATRMult=2.2;
input int MaxGridTrades=4;
input double GridStepPips=30.0;
double gLot=0.015,gGridMult=1.22;
'''
        profile='''if(RiskProfile=="Conservative"){gLot=0.015;gGridMult=1.22;}
else if(RiskProfile=="Moderate"){gLot=0.045;gGridMult=1.38;}
else if(RiskProfile=="Aggressive"){gLot=0.13;gGridMult=1.52;}
else return false;'''
        bidexpr="Bid" if lang=="m4" else "q.bid"
        askexpr="Ask" if lang=="m4" else "q.ask"
        if lang=="m4":
            helpers=init=deinit=""
            atrline="double atr=iATR(Symbol(),Period(),ATRPeriod,0); RefreshRates();"
        else:
            helpers='''int hATR=INVALID_HANDLE;'''
            init='''hATR=iATR(_Symbol,PERIOD_CURRENT,ATRPeriod); if(hATR==INVALID_HANDLE) return INIT_FAILED;'''
            deinit='''if(hATR!=INVALID_HANDLE) IndicatorRelease(hATR);'''
            atrline="double atr=0.0; MqlTick q; if(!BufferValue(hATR,0,atr) || !TickNow(q)) return;"
        tick=f'''{atrline}
int bc=CountOpen({buy}), sc=CountOpen({sell});
if(bc==0 && sc==0){{
   double fb=iLow({sym},{per},1)-ATRMult*atr, fs=iHigh({sym},{per},1)+ATRMult*atr;
   if({bidexpr}<fb) SafeSend({oby},gLot,"SZ+ Buy 0");
   else if({askexpr}>fs) SafeSend({osl},gLot,"SZ+ Sell 0");
}} else {{
   if(bc>0 && bc<MaxGridTrades){{
      double lp=LatestOpenPrice({buy});
      if(lp>0.0 && (lp-{bidexpr})/PipSize()>=GridStepPips) SafeSend({oby},gLot*MathPow(gGridMult,bc),"SZ+ Grid Buy");
   }}
   if(sc>0 && sc<MaxGridTrades){{
      double lp=LatestOpenPrice({sell});
      if(lp>0.0 && ({askexpr}-lp)/PipSize()>=GridStepPips) SafeSend({osl},gLot*MathPow(gGridMult,sc),"SZ+ Grid Sell");
   }}
}}'''
        return extra,profile,helpers,tick,init,deinit

    if kind=="stealth":
        extra='''input int MaxGridTrades=7;
input double GridStepPips=45.0;
double gLot=0.01,gGridMult=1.13;
'''
        profile='''if(RiskProfile=="Conservative"){gLot=0.01;gGridMult=1.13;}
else if(RiskProfile=="Moderate"){gLot=0.025;gGridMult=1.18;}
else if(RiskProfile=="Aggressive"){gLot=0.07;gGridMult=1.28;}
else return false;'''
        bidexpr="Bid" if lang=="m4" else "SymbolInfoDouble(_Symbol,SYMBOL_BID)"
        tick=f'''int n=CountOpen({buy});
if(n==0) SafeSend({oby},gLot,"SG Grid 1");
else if(n<MaxGridTrades){{
   double last=LatestOpenPrice({buy});
   if(last>0.0 && (last-{bidexpr})/PipSize()>=GridStepPips)
      SafeSend({oby},gLot*MathPow(gGridMult,n),"SG Grid");
}}'''
        return extra,profile,"",tick,"",""

    if kind=="ghost":
        extra='''input int MaxGridTrades=6;
input double GridStepPips=25.0;
input bool UseGhostEntry=true;
input int GhostLookback=3;
input double GhostPipMin=12.0;
input bool AdverseOnly=false; // false preserves the 4.1 absolute-spacing behavior
double gLot=0.02,gGridMult=1.41;
'''
        profile='''if(RiskProfile=="Conservative"){gLot=0.02;gGridMult=1.41;}
else if(RiskProfile=="Moderate"){gLot=0.04;gGridMult=1.56;}
else if(RiskProfile=="Aggressive"){gLot=0.10;gGridMult=1.70;}
else return false;'''
        helpers=f'''bool GhostTrigger(){{
   if(!UseGhostEntry) return true;
   for(int i=1;i<=GhostLookback;i++){{
      double body=MathAbs(iClose({sym},{per},i)-iOpen({sym},{per},i))/PipSize();
      if(body<GhostPipMin) return false;
   }}
   return true;
}}'''
        bidexpr="Bid" if lang=="m4" else "SymbolInfoDouble(_Symbol,SYMBOL_BID)"
        tick=f'''int n=CountOpen({buy});
if(n==0){{
   if(GhostTrigger()) SafeSend({oby},gLot,"GR Ghost Buy");
}} else if(n<MaxGridTrades){{
   double last=LatestOpenPrice({buy});
   bool spacing=(last>0.0 && MathAbs(({bidexpr}-last)/PipSize())>=GridStepPips);
   if(AdverseOnly && last>0.0) spacing=((last-{bidexpr})/PipSize()>=GridStepPips);
   if(spacing) SafeSend({oby},gLot*MathPow(gGridMult,n),"GR Grid");
}}'''
        return extra,profile,helpers,tick,"",""

    if kind=="chrono":
        extra='''input int ExpireBars=12;
input double RangeFilterPips=20.0;
double gLot=0.02;
'''
        profile='''if(RiskProfile=="Conservative"){gLot=0.02;gTrailStart=15.0;gTrailStep=3.0;}
else if(RiskProfile=="Moderate"){gLot=0.05;gTrailStart=10.0;gTrailStep=2.0;}
else if(RiskProfile=="Aggressive"){gLot=0.10;gTrailStart=8.0;gTrailStep=1.0;}
else return false;'''
        if lang=="m4":
            helpers='''void ExpireChrono(){
   if(!TradeActionsAllowed()) return;
   for(int i=OrdersTotal()-1;i>=0;i--){
      if(!OrderSelect(i,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderSymbol()!=Symbol() || OrderMagicNumber()!=MagicNumber || OrderType()!=OP_BUY) continue;
      int sh=iBarShift(Symbol(),Period(),OrderOpenTime(),false);
      if(sh>=ExpireBars) SafeClose(OrderTicket());
   }
}'''
            tick='''if(CountOpen(-1)==0){
   double range=(iHigh(Symbol(),Period(),1)-iLow(Symbol(),Period(),1))/PipSize();
   if(range<RangeFilterPips) SafeSend(OP_BUY,gLot,"ChronoPulse Buy");
}'''
        else:
            helpers='''void ExpireChrono(){
   if(!TradeActionsAllowed()) return;
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong ticket=PositionGetTicket(i); if(!OwnPosition(ticket,POSITION_TYPE_BUY)) continue;
      datetime tm=(datetime)PositionGetInteger(POSITION_TIME);
      int sh=iBarShift(_Symbol,PERIOD_CURRENT,tm,false);
      if(sh>=ExpireBars) SafeClose(ticket);
   }
}'''
            tick='''if(CountOpen(-1)==0){
   double range=(iHigh(_Symbol,PERIOD_CURRENT,1)-iLow(_Symbol,PERIOD_CURRENT,1))/PipSize();
   if(range<RangeFilterPips) SafeSend(ORDER_TYPE_BUY,gLot,"ChronoPulse Buy");
}'''
        return extra,profile,helpers,tick,"",""

    raise KeyError(kind)

def render_mq4(s):
    extra,profile,helpers,tick,init,deinit = strategy_parts(s["kind"],"m4")
    pre = f'''// Aether Quantus - {s["name"]}
// R6 production candidate. Core 4.1 strategy retained; execution defects hardened.
// Generated deterministically by aether-r6/generate_eas.py
#property strict
#property version "6.10"
string StrategyName="{s["name"]}";
{common_inputs(s)}
{extra}
'''
    apply = f'''bool ApplyProfile(){{
   gMaxDD=MaxDrawdownPercent; gTrailStart=TrailStartPips; gTrailStep=TrailStepPips;
   {profile}
   return true;
}}
'''
    initfn = f'''int OnInit(){{
   if(!ApplyProfile()){{ Print(StrategyName,": invalid RiskProfile ",RiskProfile); return INIT_PARAMETERS_INCORRECT; }}
   {init}
   return INIT_SUCCEEDED;
}}
void OnDeinit(const int reason){{ {deinit} Comment(""); }}
'''
    special_manage = "ExpireChrono();" if s["kind"]=="chrono" else ""
    ontick = f'''void OnTick(){{
   ManageStops();
   {special_manage}
   UpdateHUD("R6 production candidate");
   if(!EntryGate()) return;
   {tick}
}}
'''
    return pre + MQL4_COMMON + "\n" + helpers + "\n" + apply + initfn + ontick

def render_mq5(s):
    extra,profile,helpers,tick,init,deinit = strategy_parts(s["kind"],"m5")
    pre = f'''// Aether Quantus - {s["name"]} MT5
// Native MQL5 R6 production candidate. Requires hedging for multi-position grid strategies.
// Generated deterministically by aether-r6/generate_eas.py
#property strict
#property version "6.10"
string StrategyName="{s["name"]} MT5";
{common_inputs(s)}
{extra}
'''
    needs_hedge = s["kind"] in {"gearbox","king","strikeplus","stealth","ghost"}
    hedge = '''if(RequireHedging && AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING){
      Print(StrategyName,": hedging account required for multi-position strategy"); return INIT_FAILED;
   }''' if needs_hedge else ""
    if needs_hedge:
        pre += "input bool RequireHedging=true;\n"
    apply = f'''bool ApplyProfile(){{
   gMaxDD=MaxDrawdownPercent; gTrailStart=TrailStartPips; gTrailStep=TrailStepPips;
   {profile}
   return true;
}}
'''
    initfn=f'''int OnInit(){{
   if(!ApplyProfile()){{ Print(StrategyName,": invalid RiskProfile ",RiskProfile); return INIT_PARAMETERS_INCORRECT; }}
   {hedge}
   {init}
   return INIT_SUCCEEDED;
}}
void OnDeinit(const int reason){{ {deinit} Comment(""); }}
'''
    special_manage = "ExpireChrono();" if s["kind"]=="chrono" else ""
    ontick=f'''void OnTick(){{
   ManageStops();
   {special_manage}
   UpdateHUD("R6 native MT5 candidate");
   if(!EntryGate()) return;
   {tick}
}}
'''
    return pre + MQL5_COMMON + "\n" + helpers + "\n" + apply + initfn + ontick

for d in (MT4,MT5):
    for p in d.glob("*.mq?"):
        p.unlink()

manifest=[]
for s in STRATS:
    p4=MT4/(s["key"]+"_R6.mq4")
    p5=MT5/(s["key"]+"_R6.mq5")
    p4.write_text(render_mq4(s),encoding="utf-8")
    p5.write_text(render_mq5(s),encoding="utf-8")
    manifest.append((p4.name,p5.name,s["kind"]))
print("generated",len(STRATS),"MT4 and",len(STRATS),"MT5 candidates")
for row in manifest: print(*row)
